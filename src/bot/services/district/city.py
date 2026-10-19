"""Круг и выше — карта страны, владельцы города, бой с ботами всего города (сервис).

raw-notes «Фазы»: «круг уже сражается с другими городами и другими кругами... есть карта
страны, игрок выбирает город и начинает сражения... король лутает города сразу со всеми
районами в них». Подтверждено пользователем 2026-09-29 (AskUserQuestion): круг бьётся за
город **с каждым владельцем отдельно** — боты города одним боем против всех ботов разом
(забирает все их районы), игрок — вызовом за все его районы в городе
(`challenge.issue_city_challenge`, тот же час на принятие и лагерь защиты при игноре).
Проиграл нападение — теряет только статистов, районы остаются при нём.
"""
from __future__ import annotations

import random

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin.live_config import battle_cooldown_seconds
from bot.services.absolute import after_battle
from bot.constant.position_skill import VS_CITY
from bot.services.position_skill.battle import journal, matchup
from bot.constant.cooldown import CD_BATTLE
from bot.services.cooldown import schedule as schedule_ready
from bot.cache.keys import battle_cooldown
from bot.config.characteristic import extra_power_for_rank
from bot.config.game import BOT_DISTRICT_ARMY
from bot.constant.extra import CAMP_ATTACK
from bot.db.models.user import User
from bot.db.repositories.district import (
    capture_all_bots_in_city,
    city_owner_groups,
    country_city_stats,
)
from bot.db.repositories.district import challenge as challenge_repo
from bot.constant.activity import ACT_BATTLE, ACT_CAPTURE
from bot.constant.dev_quest import TASK_WIN_PVE
from bot.services.dev_quest import emit as quest_event
from bot.services.activity import log as log_activity
from bot.texts.activity import LOG_CITY_BOTS, LOST, WON
from bot.services.business import accrue
from bot.services.characteristic import get_combat_profile
from bot.services.city import get_city
from bot.services.combat import CombatStack, base_chances, simulate_battle
from bot.services.country import get_country
from bot.services.district.challenge import CityNotInCountryError, NotCityConquerorError
from bot.services.district.district import (
    BattleOnCooldownError,
    EmperorNoConquestError,
    NoAttackersError,
    apply_losses,
    get_influence,
    load_camp,
)
from bot.services.district.throne import LiberationOutcome, ThroneOutcome, promote_or_throne
from bot.services.phase import can_conquer_cities, is_emperor


class NoBotsInCityError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CityStat:
    city_id: int
    name: str
    district_count: int
    bots: int
    mine: int
    owners: int

    @property
    def fully_mine(self) -> bool:
        return self.mine == self.district_count


@dataclass(frozen=True, slots=True)
class CountryMap:
    country_name: str
    cities: list[CityStat]
    cities_mine: int  # целиком твоих городов


@dataclass(frozen=True, slots=True)
class OwnerGroup:
    owner_id: int
    label: str
    districts: int
    is_mine: bool
    challenged: bool  # на его районы в этом городе уже висит вызов круга


@dataclass(frozen=True, slots=True)
class CityOwners:
    city_id: int
    name: str
    district_count: int
    bots: int
    bot_rank: str
    bot_quantity: int  # суммарно по всем районам ботов
    bot_power: int
    owners: list[OwnerGroup]


@dataclass(frozen=True, slots=True)
class CityBotReport:
    city_name: str
    won: bool
    captured: int
    rounds: int
    attacker_quantity: int
    attacker_power: int
    attacker_dead: int
    attacker_fled: int
    attacker_remaining_power: int
    defender_power: int
    defender_dead: int
    influence: int
    promoted_to: str | None
    free_attack: bool = False
    throne: ThroneOutcome | None = None
    liberations: tuple[LiberationOutcome, ...] = ()  # бои за освобождение страны с чужими императорами
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)


def _city_bot_army(district_count: int, bot_districts: int) -> tuple[str, int]:
    """Армия ботов города = армия одного района × число районов у ботов (тот же ранг)."""
    rank, per_district = BOT_DISTRICT_ARMY[district_count]
    return rank, per_district * bot_districts


async def get_country_map(session: AsyncSession, user: User) -> CountryMap:
    rows = await country_city_stats(session, user.country_code, user.id)
    cities = [CityStat(r.city_id, r.name, r.district_count, r.bots, r.mine, r.owners) for r in rows]
    country = get_country(user.country_code)
    return CountryMap(
        country_name=country.name if country else user.country_code,
        cities=cities,
        cities_mine=sum(c.fully_mine for c in cities),
    )


async def get_city_owners(session: AsyncSession, user: User, city_id: int) -> CityOwners:
    city = await get_city(session, city_id)
    if city is None or city.country_code != user.country_code:
        raise CityNotInCountryError
    groups = await city_owner_groups(session, city_id)
    challenged = await challenge_repo.list_pending_city_defenders(session, city_id)
    bots = next((g.districts for g in groups if g.owner_id is None), 0)
    rank, quantity = _city_bot_army(city.district_count, bots)
    owners = [
        OwnerGroup(
            owner_id=g.owner_id,
            label=g.owner_gang or g.owner_name or "—",
            districts=g.districts,
            is_mine=g.owner_id == user.id,
            challenged=g.owner_id in challenged,
        )
        for g in groups
        if g.owner_id is not None
    ]
    return CityOwners(
        city_id=city.id,
        name=city.name,
        district_count=city.district_count,
        bots=bots,
        bot_rank=rank,
        bot_quantity=quantity,
        bot_power=quantity * extra_power_for_rank(rank),
        owners=owners,
    )


async def attack_city_bots(session: AsyncSession, redis: Redis, user: User, city_id: int) -> CityBotReport:
    """Составная операция (правило 10), тот же порядок, что `attack_district`: проверки
    (не стоят КД) → КД `SET NX EX` по фазе → бой против суммарной армии ботов города →
    потери → начисление бизнеса → захват ВСЕХ районов ботов одним UPDATE → проверка
    перехода фазы → один commit."""
    if is_emperor(user.phase):
        raise EmperorNoConquestError
    if not can_conquer_cities(user.phase):
        raise NotCityConquerorError
    city = await get_city(session, city_id)
    if city is None or city.country_code != user.country_code:
        raise CityNotInCountryError
    groups = await city_owner_groups(session, city_id)
    bots = next((g.districts for g in groups if g.owner_id is None), 0)
    if bots == 0:
        raise NoBotsInCityError

    stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise NoAttackersError

    key = battle_cooldown(user.id)
    profile = await get_combat_profile(session, user.id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(battle_cooldown_seconds(user.phase), profile.eco.battle_cooldown)):
        raise BattleOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))

    rank, quantity = _city_bot_army(city.district_count, bots)
    defender = [CombatStack(key="bot", unit_power=extra_power_for_rank(rank), quantity=quantity)]
    m = matchup(profile, vs=(VS_CITY,), defender_chances=base_chances(), attacker_stacks=stacks)
    result = simulate_battle(stacks, defender, attacker_chances=m.attacker, defender_chances=m.defender)
    await apply_losses(session, user.id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, attacker_id=user.id, attacker_stacks=stacks)

    captured = 0
    promoted_to = None
    throne = None
    liberations: tuple = ()
    if result.attacker_won:
        await accrue(session, user.id)
        captured = await capture_all_bots_in_city(session, city_id, user.id)
        if captured:
            promoted_to, throne, liberations = await promote_or_throne(session, user.id, city_id)
    if result.attacker_won:
        await quest_event(session, user.id, TASK_WIN_PVE)
    await log_activity(
        session, user.id, ACT_CAPTURE if captured else ACT_BATTLE,
        LOG_CITY_BOTS.format(city=city.name, outcome=WON if result.attacker_won else LOST, count=captured),
    )
    await session.commit()
    free_attack = profile.rolls_free_attack()
    # «Неудержимый» / «Двойной захват» (Военачальник): шанс, что победа над ботами не ставит КД.
    if not free_attack and result.attacker_won and profile.build.positions is not None:
        pos = profile.build.positions
        free_attack = random.random() < min(0.5, pos.get("no_cd_bots") + pos.get("no_cd_on_win"))
    if free_attack:
        await redis.delete(key)
    else:
        await schedule_ready(redis, user.id, CD_BATTLE, await redis.ttl(key))

    return CityBotReport(
        journal=journal(result, m.spy) + abs_lines,
        city_name=city.name,
        won=result.attacker_won,
        captured=captured,
        rounds=result.rounds,
        attacker_quantity=result.attacker.initial_quantity,
        attacker_power=result.attacker.initial_power,
        attacker_dead=result.attacker.total_dead,
        attacker_fled=result.attacker.fled,
        attacker_remaining_power=result.attacker.remaining_power,
        defender_power=result.defender.initial_power,
        defender_dead=result.defender.total_dead,
        influence=await get_influence(session, user.id),
        promoted_to=promoted_to,
        free_attack=free_attack,
        throne=throne,
        liberations=liberations,
    )
