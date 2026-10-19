"""Районы — карта города, влияние, захват района у ботов (сервис).

raw-notes «Карта»: игрок в фазе банды не может покинуть свой город и захватывает его
районы; незахваченные держат боты, захваченные — другие игроки. Здесь — захват у ботов
(PvE, бой сразу). Район другого игрока — через вызов (`services/district/challenge.py`:
уведомление защитнику, час на принятие, при игноре — бой против его лагеря защиты).
"""
from __future__ import annotations

import random

from dataclasses import dataclass, replace

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin.live_config import battle_cooldown_seconds
from bot.services.absolute import after_battle
from bot.services.build import get_build
from bot.constant.position_skill import VS_DISTRICT
from bot.services.position_skill.battle import journal, matchup
from bot.constant.cooldown import CD_BATTLE
from bot.services.cooldown import schedule as schedule_ready
from bot.cache.keys import battle_cooldown
from bot.config.characteristic import extra_power_for_rank
from bot.config.game import BOT_DISTRICT_ARMY, INFLUENCE_PER_DISTRICT, INFLUENCE_STARTING
from bot.constant.extra import CAMP_ATTACK
from bot.db.models.user import User
from bot.db.repositories.district import challenge as challenge_repo
from bot.db.repositories.district import (
    DistrictRow,
    capture_from_bots,
    count_owned,
    get_row,
    list_by_city,
    seed_districts,
)
from bot.constant.activity import ACT_BATTLE, ACT_CAPTURE
from bot.constant.dev_quest import TASK_WIN_PVE
from bot.services.dev_quest import emit as quest_event
from bot.services.activity import log as log_activity
from bot.services.stealth import is_hidden
from bot.texts.stealth import STEALTH_LABEL
from bot.texts.activity import LOG_CAPTURED, LOG_PVE, LOST, WON
from bot.services.characteristic import get_combat_profile
from bot.services.business import accrue, parliament_influence
from bot.services.city import get_city
from bot.services.district.army import apply_losses, load_camp
from bot.services.combat import CombatStack, base_chances, simulate_battle
from bot.services.district.throne import LiberationOutcome, ThroneOutcome, promote_or_throne
from bot.services.phase import is_city_conqueror, is_emperor


class DistrictNotFoundError(Exception):
    pass


class NotYourCityError(Exception):
    pass


class OwnDistrictError(Exception):
    pass


class PlayerDistrictError(Exception):
    """Район принадлежит другому игроку — на него не нападают напрямую, а бросают вызов
    (`services/district/challenge.issue_challenge`)."""


class NoAttackersError(Exception):
    pass


class EmperorNoConquestError(Exception):
    """Император не захватывает районы и города своей страны — его войны против других
    императоров (`docs/design/fist_emperor.md`)."""


class CityConquerorError(Exception):
    """Круг и выше не нападают на отдельные районы — они воюют за город целиком, с каждым
    владельцем отдельно (карта страны → город, `services/district/city.py`)."""


class BattleOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class DistrictView:
    id: int
    number: int
    owner_id: int | None
    owner_label: str | None  # название банды владельца (или его имя, если банды нет)
    is_mine: bool
    bot_rank: str | None
    bot_quantity: int | None
    bot_power: int | None
    challenged: bool = False  # на район уже висит PvP-вызов (заполняется только для карточки)


@dataclass(frozen=True, slots=True)
class CityMap:
    city_name: str
    districts: list[DistrictView]
    mine: int
    bots: int
    others: int
    sole_owner_label: str | None  # весь город у одного игрока (raw-notes: "должно быть видно")


@dataclass(frozen=True, slots=True)
class AttackReport:
    district_number: int
    won: bool
    captured: bool
    taken_by_other: bool  # победил ботов, но район успел забрать другой игрок
    rounds: int
    attacker_quantity: int
    attacker_power: int
    attacker_dead: int
    attacker_fled: int
    attacker_remaining_power: int
    defender_power: int
    defender_dead: int
    influence: int
    promoted_to: str | None = None  # захват закрыл город — банда стала кругом
    free_attack: bool = False  # Ловкость: КД после этой атаки не поставлен
    throne: ThroneOutcome | None = None  # захват закрыл страну, трон был занят — бой за трон
    liberations: tuple[LiberationOutcome, ...] = ()  # бои за освобождение страны с чужими императорами
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)


async def seed(session: AsyncSession) -> None:
    """Бутстрап районов — вызывается вручную через `python manager.py seed` ПОСЛЕ
    стран/городов (FK на `cities.id`, district_count берётся из городов)."""
    await seed_districts(session)


@dataclass(frozen=True, slots=True)
class Territory:
    districts: int
    influence: int


def _influence_for(districts: int, parliament_bonus: int) -> int:
    """raw-notes: «изначальный показатель 10», растёт от захваченных районов — +1 за
    район (подтверждено пользователем 2026-09-29). Бонус за целый город не вводился
    (выбран вариант без него). Плюс парламенты (+1 за здание, домен `business`) —
    raw-notes: «парламент... даёт влияние»."""
    return INFLUENCE_STARTING + INFLUENCE_PER_DISTRICT * districts + parliament_bonus


async def get_territory(session: AsyncSession, user_id: int) -> Territory:
    districts = await count_owned(session, user_id)
    positions = (await get_build(session, user_id)).positions
    skill_influence = int(positions.get("influence")) if positions is not None else 0  # «Авторитет» Главы
    return Territory(
        districts=districts,
        influence=_influence_for(districts, await parliament_influence(session, user_id)) + skill_influence,
    )


async def get_influence(session: AsyncSession, user_id: int) -> int:
    return (await get_territory(session, user_id)).influence


def _bot_army(district_count: int) -> tuple[str, int]:
    return BOT_DISTRICT_ARMY[district_count]


def _view(row: DistrictRow, viewer_id: int, district_count: int) -> DistrictView:
    if row.owner_id is None:
        rank, quantity = _bot_army(district_count)
        return DistrictView(
            id=row.id, number=row.number, owner_id=None, owner_label=None, is_mine=False,
            bot_rank=rank, bot_quantity=quantity, bot_power=quantity * extra_power_for_rank(rank),
        )
    return DistrictView(
        id=row.id, number=row.number, owner_id=row.owner_id,
        owner_label=row.owner_gang or row.owner_name or "—", is_mine=row.owner_id == viewer_id,
        bot_rank=None, bot_quantity=None, bot_power=None,
    )


async def _hide_stealthy(views: list[DistrictView], session: AsyncSession) -> list[DistrictView]:
    """Скрытые владельцы (Курода) на карте — «Неизвестный»; свои районы — как есть."""
    hidden = {}
    for owner_id in {v.owner_id for v in views if v.owner_id is not None and not v.is_mine}:
        hidden[owner_id] = await is_hidden(session, owner_id)
    return [replace(v, owner_label=STEALTH_LABEL) if hidden.get(v.owner_id) else v for v in views]


async def get_city_map(session: AsyncSession, user: User) -> CityMap:
    city = await get_city(session, user.city_id)
    rows = await list_by_city(session, city.id)
    views = await _hide_stealthy([_view(r, user.id, city.district_count) for r in rows], session)
    owners = {v.owner_id for v in views}
    sole = views[0].owner_label if len(owners) == 1 and views and views[0].owner_id is not None else None
    return CityMap(
        city_name=city.name,
        districts=views,
        mine=sum(v.is_mine for v in views),
        bots=sum(v.owner_id is None for v in views),
        others=sum(v.owner_id is not None and not v.is_mine for v in views),
        sole_owner_label=sole,
    )


async def get_district_view(session: AsyncSession, user: User, district_id: int) -> DistrictView:
    row = await get_row(session, district_id)
    # Свой город — любой район; чужой город — только свой район (у круга районы в разных
    # городах, их карточки открываются из экрана бизнеса).
    if row is None or (row.city_id != user.city_id and row.owner_id != user.id):
        raise DistrictNotFoundError
    city = await get_city(session, row.city_id)
    view = (await _hide_stealthy([_view(row, user.id, city.district_count)], session))[0]
    if row.owner_id is not None and await challenge_repo.get_pending_for_district(session, row.id) is not None:
        view = replace(view, challenged=True)
    return view


async def attack_district(session: AsyncSession, redis: Redis, user: User, district_id: int) -> AttackReport:
    """Составная операция (правило 10): проверки → КД → бой → списание погибших → захват
    → один commit. Все проверки, которые не должны тратить КД (чужой город, свой
    район, пустой лагерь атаки), — ДО выставления КД в Redis."""
    row = await get_row(session, district_id)
    if row is None:
        raise DistrictNotFoundError
    if row.city_id != user.city_id:
        # Фаза банды не позволяет покинуть город (raw-notes «Фазы»).
        raise NotYourCityError
    if row.owner_id == user.id:
        raise OwnDistrictError
    if is_emperor(user.phase):
        raise EmperorNoConquestError
    if is_city_conqueror(user.phase):
        raise CityConquerorError
    if row.owner_id is not None:
        raise PlayerDistrictError

    stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise NoAttackersError

    key = battle_cooldown(user.id)
    profile = await get_combat_profile(session, user.id)
    acquired = await redis.set(key, "1", nx=True, ex=profile.cooldown(battle_cooldown_seconds(user.phase), profile.eco.battle_cooldown))
    if not acquired:
        ttl = await redis.ttl(key)
        raise BattleOnCooldownError(retry_after_seconds=max(0, ttl))

    city = await get_city(session, row.city_id)
    bot_rank, bot_quantity = _bot_army(city.district_count)
    defender = [CombatStack(key="bot", unit_power=extra_power_for_rank(bot_rank), quantity=bot_quantity)]
    m = matchup(profile, vs=(VS_DISTRICT,), defender_chances=base_chances(), attacker_stacks=stacks)
    result = simulate_battle(stacks, defender, attacker_chances=m.attacker, defender_chances=m.defender)
    await apply_losses(session, user.id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, attacker_id=user.id, attacker_stacks=stacks)

    captured = False
    if result.attacker_won:
        # Районы ботов обычно пусты, но если на районе остались здания (район вернулся
        # ботам) — они перейдут захватчику; начисление ДО захвата, чтобы они не
        # "заработали" ему задним числом (тот же порядок, что у PvP).
        await accrue(session, user.id)
        captured = await capture_from_bots(session, row.id, user.id)
    promoted_to, throne, liberations = await promote_or_throne(session, user.id, row.city_id) if captured else (None, None, ())
    if result.attacker_won:
        await quest_event(session, user.id, TASK_WIN_PVE)
    await log_activity(
        session, user.id, ACT_CAPTURE if captured else ACT_BATTLE,
        LOG_PVE.format(number=row.number, outcome=WON if result.attacker_won else LOST, captured=LOG_CAPTURED if captured else ""),
    )
    await session.commit()
    # Ловкость: «две атаки сразу, игнорируя КД» — с шансом КД после этой атаки снимается.
    free_attack = profile.rolls_free_attack()
    # «Неудержимый» / «Двойной захват» (Военачальник): шанс, что победа над ботами не ставит КД.
    if not free_attack and result.attacker_won and profile.build.positions is not None:
        pos = profile.build.positions
        free_attack = random.random() < min(0.5, pos.get("no_cd_bots") + pos.get("no_cd_on_win"))
    if free_attack:
        await redis.delete(key)
    else:
        await schedule_ready(redis, user.id, CD_BATTLE, await redis.ttl(key))

    return AttackReport(
        journal=journal(result, m.spy) + abs_lines,
        district_number=row.number,
        won=result.attacker_won,
        captured=captured,
        taken_by_other=result.attacker_won and not captured,
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
