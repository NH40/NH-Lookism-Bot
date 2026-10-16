"""PvP — вызов на район другого игрока (сервис).

raw-notes «Карта»: «если это игрок, то ему приходит сообщение, и в течение 1 часа он
должен начать сражение... если игрок не принял сражение, то идёт сражение атакующий vs
защищающийся — берётся другой лагерь, лагерь защиты». Подтверждено пользователем
2026-09-29 (AskUserQuestion): игнор = автобой против лагеря защиты (не передача района
без боя); у нападающего один исходящий вызов за раз; КД на сражения после боя — только
нападающему (защитник боя не выбирал).

Жизненный цикл: `issue_challenge` (нападающий) → либо `accept_challenge` (защитник принял
до `expires_at`: бьются лагеря атаки обоих), либо `resolve_expired` (фоновый sweep в
`main.py`: бьётся лагерь защиты защитника). Оба пути идут через `_resolve`, который
первым делом атомарно "забирает" вызов (`challenge_repo.claim`) — один вызов не может
разрешиться двумя боями.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.services.absolute import after_battle
from bot.services.build import get_build
from bot.services.intel.scout import has_report as has_scout_report
from bot.constant.position_skill import ROLE_ATTACK, ROLE_DEFENSE, VS_PVP
from bot.services.position_skill.battle import journal, matchup
from bot.constant.cooldown import CD_BATTLE
from bot.services.cooldown import schedule as schedule_ready
from bot.cache.keys import battle_cooldown
from bot.config.game import BATTLE_COOLDOWN_SECONDS, CHALLENGE_ACCEPT_SECONDS, CHALLENGE_SWEEP_BATCH
from bot.constant.district import RESOLUTION_ACCEPTED, RESOLUTION_TIMEOUT, RESOLUTION_VOID, SCOPE_CITY, SCOPE_DISTRICT
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.db.models.user import User
from bot.db.repositories.district import challenge as challenge_repo
from bot.db.repositories.district import count_owned_in_city, get_row, transfer_all_in_city, transfer_owner
from bot.db.repositories.phase import get_phase
from bot.db.repositories.user import get_by_id
from bot.constant.activity import ACT_BATTLE, ACT_CAPTURE
from bot.constant.dev_quest import TASK_PVP_CHALLENGE, TASK_WIN_PVP
from bot.services.dev_quest import emit as quest_event
from bot.services.activity import log as log_activity
from bot.services.activity import remember_opponents
from bot.services.stealth import label as stealth_label
from bot.texts.activity import LOG_PVP_ATTACKER, LOG_PVP_DEFENDER, LOST, WON
from bot.services.business import accrue_many
from bot.services.characteristic import get_combat_profile
from bot.services.city import get_city
from bot.services.combat import simulate_battle
from bot.services.district.district import (
    BattleOnCooldownError,
    CityConquerorError,
    DistrictNotFoundError,
    EmperorNoConquestError,
    NoAttackersError,
    NotYourCityError,
    OwnDistrictError,
    apply_losses,
    load_camp,
)
from bot.services.extra import CampStats, get_army_stats
from bot.services.gang import get_gang
from bot.services.mastery import record_pvp_win
from bot.services.district.throne import LiberationOutcome, ThroneOutcome, promote_or_throne
from bot.services.phase import can_conquer_cities, is_city_conqueror, is_emperor

log = logging.getLogger(__name__)


class BotDistrictError(Exception):
    """Район у ботов — вызов не нужен, на него нападают напрямую (`attack_district`)."""


class DistrictAlreadyChallengedError(Exception):
    pass


class OutgoingChallengeExistsError(Exception):
    pass


class NotCityConquerorError(Exception):
    """Вызов за город целиком — только для круга и выше; банда воюет за отдельные районы."""


class CityNotInCountryError(Exception):
    pass


class NothingToTakeError(Exception):
    """У выбранного игрока нет районов в этом городе (или это ты сам)."""


class CityAlreadyChallengedError(Exception):
    """На районы этого игрока в городе уже висит вызов круга."""


class ChallengeNotFoundError(Exception):
    """Вызова нет, он не твой, или уже разрешён (принят, истёк и обработан sweep'ом)."""


@dataclass(frozen=True, slots=True)
class ChallengeIssued:
    challenge_id: int
    scope: str
    district_number: int  # 0 для вызова за город
    city_name: str
    districts: int  # сколько районов на кону (1 для вызова за район)
    defender_id: int
    attacker_label: str
    defender_label: str
    accept_seconds: int
    defender_attack: CampStats
    defender_defense: CampStats


@dataclass(frozen=True, slots=True)
class ChallengeOutcome:
    challenge_id: int
    scope: str
    district_id: int | None
    city_id: int | None
    city_name: str
    district_number: int
    attacker_id: int
    defender_id: int
    attacker_label: str
    defender_label: str
    resolution: str
    attacker_won: bool
    captured: bool
    rounds: int
    attacker_quantity: int
    attacker_power: int
    attacker_dead: int
    attacker_fled: int
    defender_quantity: int
    defender_power: int
    defender_dead: int
    defender_fled: int
    captured_districts: int = 0
    attacker_promoted_to: str | None = None
    free_attack: bool = False
    throne: ThroneOutcome | None = None
    liberations: tuple[LiberationOutcome, ...] = ()  # бои за освобождение страны с чужими императорами
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)
    defender_journal: tuple[str, ...] = ()  # тот же бой глазами защитника


async def _label(session: AsyncSession, user_id: int) -> str:
    gang = await get_gang(session, user_id)
    if gang is not None:
        return await stealth_label(session, user_id, gang.name)
    user = await get_by_id(session, user_id)
    return await stealth_label(session, user_id, (user.display_name if user else None) or "—")


async def _accept_window(session: AsyncSession, attacker_id: int, defender_id: int) -> int:
    """Время защитнику на принятие: Скорость нападающего (−1%/ранг), навыки защитника
    («Переговорщик», «Часовой», «Ранняя тревога» — +%), шпион нападающего «Ускоренный
    марш» (−%, с шансом, срывается контрразведкой) — тот бросается здесь, при вызове."""
    import random as _random

    from bot.services.position_skill import NO_EFFECTS

    attacker = await get_combat_profile(session, attacker_id)
    window = attacker.accept_window(CHALLENGE_ACCEPT_SECONDS)
    defender_pos = (await get_build(session, defender_id)).positions or NO_EFFECTS
    window *= 1 + min(0.5, defender_pos.get("accept_window"))
    attacker_pos = attacker.build.positions or NO_EFFECTS
    for s in attacker_pos.spies:
        if "enemy_accept_window" in s.skill.fx:
            chance = max(0.0, min(0.9, s.skill.fx.get("p", 0) * s.power + attacker_pos.get("spy_chance")) - defender_pos.get("anti_spy"))
            if _random.random() < chance:
                window *= 1 + max(-0.5, s.value("enemy_accept_window"))
    return max(60, round(window))


async def issue_challenge(session: AsyncSession, redis: Redis, attacker: User, district_id: int) -> ChallengeIssued:
    """Проверки → вставка вызова (частичные уникальные индексы ловят гонку) → один commit.
    КД на сражения ПРОВЕРЯЕТСЯ, но не ставится — он ставится после боя (raw-notes: «после
    сражения у игрока начинается кд»); повторно бросить вызов, пока висит текущий, не
    даёт уникальный индекс, а не КД."""
    row = await get_row(session, district_id)
    if row is None:
        raise DistrictNotFoundError
    if row.city_id != attacker.city_id:
        raise NotYourCityError
    if row.owner_id == attacker.id:
        raise OwnDistrictError
    if is_emperor(attacker.phase):
        raise EmperorNoConquestError
    if is_city_conqueror(attacker.phase):
        raise CityConquerorError
    if row.owner_id is None:
        raise BotDistrictError

    if not await load_camp(session, attacker.id, CAMP_ATTACK, for_update=False):
        raise NoAttackersError
    ttl = await redis.ttl(battle_cooldown(attacker.id))
    if ttl > 0:
        raise BattleOnCooldownError(retry_after_seconds=ttl)

    # Дружелюбные проверки ДО вставки — чтобы сказать игроку, что именно не так; сама
    # гарантия всё равно в индексах (вставка ниже вернёт None при гонке).
    if await challenge_repo.get_pending_for_attacker(session, attacker.id) is not None:
        raise OutgoingChallengeExistsError
    if await challenge_repo.get_pending_for_district(session, district_id) is not None:
        raise DistrictAlreadyChallengedError

    # Скорость нападающего: −1% времени защитнику на принятие за ранг (raw-notes).
    window = await _accept_window(session, attacker.id, row.owner_id)
    challenge_id = await challenge_repo.create(
        session,
        city_id=row.city_id,
        district_id=district_id,
        attacker_id=attacker.id,
        defender_id=row.owner_id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=window),
    )
    if challenge_id is None:
        # Без `session.rollback()`: `ON CONFLICT DO NOTHING` транзакцию не обрывает, а
        # rollback экспайрит ВСЕ ORM-объекты сессии (включая переданный `attacker`) —
        # следующее обращение к `attacker.id` полезло бы в ленивую подгрузку, что в
        # async-режиме падает `MissingGreenlet` (пойман e2e-тестом гонки 2026-09-29).
        if await challenge_repo.get_pending_for_attacker(session, attacker.id) is not None:
            raise OutgoingChallengeExistsError
        raise DistrictAlreadyChallengedError

    defender_army = await get_army_stats(session, row.owner_id)
    city = await get_city(session, row.city_id)
    issued = ChallengeIssued(
        challenge_id=challenge_id,
        scope=SCOPE_DISTRICT,
        district_number=row.number,
        city_name=city.name,
        districts=1,
        defender_id=row.owner_id,
        attacker_label=await _label(session, attacker.id),
        defender_label=row.owner_gang or row.owner_name or "—",
        accept_seconds=window,
        defender_attack=defender_army.attack,
        defender_defense=defender_army.defense,
    )
    await quest_event(session, attacker.id, TASK_PVP_CHALLENGE)
    await session.commit()
    return issued


async def issue_city_challenge(
    session: AsyncSession, redis: Redis, attacker: User, city_id: int, defender_id: int
) -> ChallengeIssued:
    """Вызов круга за ВСЕ районы игрока в городе (подтверждено 2026-09-29: круг бьётся за
    город с каждым владельцем отдельно). Тот же жизненный цикл, что у вызова за район: час
    на принятие, иначе бой против лагеря защиты; на кону — районы, что защитник держит в
    городе В МОМЕНТ боя. Тот же порядок проверок: всё, что не должно ничего стоить, — до
    вставки; гарантия единственности — в частичных индексах."""
    if is_emperor(attacker.phase):
        raise EmperorNoConquestError
    if not can_conquer_cities(attacker.phase):
        raise NotCityConquerorError
    city = await get_city(session, city_id)
    if city is None or city.country_code != attacker.country_code:
        raise CityNotInCountryError
    if defender_id == attacker.id:
        raise NothingToTakeError
    districts = await count_owned_in_city(session, city_id, defender_id)
    if districts == 0:
        raise NothingToTakeError

    if not await load_camp(session, attacker.id, CAMP_ATTACK, for_update=False):
        raise NoAttackersError
    ttl = await redis.ttl(battle_cooldown(attacker.id))
    if ttl > 0:
        raise BattleOnCooldownError(retry_after_seconds=ttl)
    if await challenge_repo.get_pending_for_attacker(session, attacker.id) is not None:
        raise OutgoingChallengeExistsError
    if defender_id in await challenge_repo.list_pending_city_defenders(session, city_id):
        raise CityAlreadyChallengedError

    window = await _accept_window(session, attacker.id, defender_id)
    challenge_id = await challenge_repo.create(
        session,
        city_id=city_id,
        district_id=None,
        attacker_id=attacker.id,
        defender_id=defender_id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=window),
    )
    if challenge_id is None:
        # Без rollback — см. комментарий в `issue_challenge`.
        if await challenge_repo.get_pending_for_attacker(session, attacker.id) is not None:
            raise OutgoingChallengeExistsError
        raise CityAlreadyChallengedError

    defender_army = await get_army_stats(session, defender_id)
    issued = ChallengeIssued(
        challenge_id=challenge_id,
        scope=SCOPE_CITY,
        district_number=0,
        city_name=city.name,
        districts=districts,
        defender_id=defender_id,
        attacker_label=await _label(session, attacker.id),
        defender_label=await _label(session, defender_id),
        accept_seconds=window,
        defender_attack=defender_army.attack,
        defender_defense=defender_army.defense,
    )
    await quest_event(session, attacker.id, TASK_PVP_CHALLENGE)
    await session.commit()
    return issued


async def accept_challenge(session: AsyncSession, redis: Redis, defender: User, challenge_id: int) -> ChallengeOutcome:
    """Если защитник жмёт "Принять" уже после `expires_at`, но sweep ещё не успел — вызов
    разрешается как просроченный (лагерем защиты), а не как принятый: окно в час —
    жёсткое, а не "пока sweep не дошёл"."""
    challenge = await challenge_repo.get(session, challenge_id)
    if challenge is None or challenge.defender_id != defender.id:
        raise ChallengeNotFoundError
    expired = datetime.now(timezone.utc) >= challenge.expires_at
    outcome = await _resolve(session, redis, challenge_id, RESOLUTION_TIMEOUT if expired else RESOLUTION_ACCEPTED)
    if outcome is None:
        raise ChallengeNotFoundError
    return outcome


async def resolve_expired(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> list[ChallengeOutcome]:
    """Для фонового sweep (`main.py`). Каждый вызов — своя сессия и своя транзакция: падение
    одного боя (например, дедлок) не откатывает остальные, а сам вызов остаётся
    `pending` и будет подхвачен следующим проходом."""
    async with session_factory() as session:
        ids = await challenge_repo.list_expired_ids(session, CHALLENGE_SWEEP_BATCH)
    outcomes: list[ChallengeOutcome] = []
    for challenge_id in ids:
        async with session_factory() as session:
            try:
                outcome = await _resolve(session, redis, challenge_id, RESOLUTION_TIMEOUT)
            except Exception:
                log.exception("Failed to resolve expired challenge %s", challenge_id)
                await session.rollback()
                continue
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes


async def _resolve(session: AsyncSession, redis: Redis, challenge_id: int, resolution: str) -> ChallengeOutcome | None:
    challenge = await challenge_repo.claim(session, challenge_id, resolution)
    if challenge is None:
        # Вызов уже разрешён другим путём. Rollback не нужен (UPDATE затронул 0 строк,
        # менять нечего) и вреден: он экспайрит ORM-объекты вызывающего кода (см. тот же
        # комментарий в `issue_challenge`).
        return None

    is_city = challenge.scope == SCOPE_CITY
    attacker_label = await _label(session, challenge.attacker_id)
    defender_label = await _label(session, challenge.defender_id)
    city = await get_city(session, challenge.city_id) if challenge.city_id is not None else None
    base = dict(
        challenge_id=challenge_id, scope=challenge.scope, district_id=challenge.district_id,
        city_id=challenge.city_id, city_name=city.name if city else "—",
        attacker_id=challenge.attacker_id, defender_id=challenge.defender_id,
        attacker_label=attacker_label, defender_label=defender_label,
    )

    # Аннулирование: к бою защитнику уже нечего терять — район ушёл (масштаб района) или
    # в городе у него не осталось ни одного района (масштаб города).
    row = None
    if is_city:
        void = await count_owned_in_city(session, challenge.city_id, challenge.defender_id) == 0
    else:
        row = await get_row(session, challenge.district_id)
        void = row is None or row.owner_id != challenge.defender_id
    district_number = row.number if row else 0
    if void:
        await challenge_repo.set_outcome(session, challenge_id, resolution=RESOLUTION_VOID, attacker_won=None)
        await session.commit()
        return ChallengeOutcome(
            **base, district_number=district_number, resolution=RESOLUTION_VOID, attacker_won=False, captured=False,
            rounds=0, attacker_quantity=0, attacker_power=0, attacker_dead=0, attacker_fled=0,
            defender_quantity=0, defender_power=0, defender_dead=0, defender_fled=0,
        )

    # КД нападающему — по его фазе НА МОМЕНТ боя (как у PvE): повышение этим же боем не
    # удлиняет КД задним числом.
    attacker_phase = (await get_phase(session, challenge.attacker_id))[0]
    attacker_profile = await get_combat_profile(session, challenge.attacker_id)
    defender_profile = await get_combat_profile(session, challenge.defender_id)
    defender_camp = CAMP_ATTACK if resolution == RESOLUTION_ACCEPTED else CAMP_DEFENSE
    # Блокируем стопки обоих в ОДНОМ порядке (по user_id) — иначе два встречных вызова
    # (A напал на B, B на A), разрешаемые одновременно, могли бы взять блокировки
    # крест-накрест и упереться в дедлок.
    sides = sorted([(challenge.attacker_id, CAMP_ATTACK), (challenge.defender_id, defender_camp)])
    locked = {}
    for user_id, camp in sides:
        locked[user_id] = await load_camp(session, user_id, camp, for_update=True)

    # Принял бой — защитник бьётся лагерем атаки: навыки «в защите» не работают.
    m = matchup(
        attacker_profile, defender_profile, vs=(VS_PVP,),
        defender_role=ROLE_ATTACK if resolution == RESOLUTION_ACCEPTED else ROLE_DEFENSE,
        scouted=await has_scout_report(session, challenge.attacker_id, challenge.defender_id),
        attacker_stacks=locked[challenge.attacker_id], defender_stacks=locked[challenge.defender_id],
    )
    result = simulate_battle(
        locked[challenge.attacker_id],
        locked[challenge.defender_id],
        attacker_chances=m.attacker,
        defender_chances=m.defender,
    )
    await apply_losses(session, challenge.attacker_id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, attacker_id=challenge.attacker_id, attacker_stacks=locked[challenge.attacker_id], defender_id=challenge.defender_id)
    await apply_losses(session, challenge.defender_id, defender_camp, result.defender.dead)

    captured_districts = 0
    promoted_to = None
    throne = None
    liberations: tuple = ()
    if result.attacker_won:
        # Бизнесы уходят победителю вместе с районами (подтверждено 2026-09-29) — сначала
        # начисляем доход ОБОИМ по старому набору зданий: проигравший получает заработанное
        # до этой секунды, победитель не получает доход захваченных зданий задним числом.
        # Порядок блокировок: стопки → строки игроков → районы (как у стройки).
        await accrue_many(session, [challenge.attacker_id, challenge.defender_id])
        if is_city:
            captured_districts = await transfer_all_in_city(
                session, challenge.city_id, challenge.defender_id, challenge.attacker_id
            )
        else:
            captured_districts = int(
                await transfer_owner(session, challenge.district_id, challenge.defender_id, challenge.attacker_id)
            )
        if captured_districts:
            promoted_to, throne, liberations = await promote_or_throne(session, challenge.attacker_id, challenge.city_id or row.city_id)
    if result.attacker_won:
        # Задания цепочки мастерства (этап 3): победы нападающим и «победа над равным»
        # (±10% мощи — сравниваются армии, вышедшие в этот бой).
        await record_pvp_win(session, challenge.attacker_id, result.attacker.initial_power, result.defender.initial_power)
    await challenge_repo.set_outcome(session, challenge_id, resolution=resolution, attacker_won=result.attacker_won)
    won = result.attacker_won
    await log_activity(
        session, challenge.attacker_id, ACT_CAPTURE if captured_districts else ACT_BATTLE,
        LOG_PVP_ATTACKER.format(defender=defender_label, outcome=WON if won else LOST, count=captured_districts),
    )
    await log_activity(
        session, challenge.defender_id, ACT_BATTLE,
        LOG_PVP_DEFENDER.format(attacker=attacker_label, outcome=LOST if won else WON, count=captured_districts),
    )
    await remember_opponents(session, challenge.attacker_id, challenge.defender_id)
    if won:
        await quest_event(session, challenge.attacker_id, TASK_WIN_PVP)
    await session.commit()

    # Правило 10: Redis — только после успешного commit. КД — только нападающему, с
    # мастерством Скорости; Ловкость — с шансом КД не ставится вовсе («вторая атака»).
    free_attack = attacker_profile.rolls_free_attack()
    if not free_attack:
        cd = attacker_profile.cooldown(BATTLE_COOLDOWN_SECONDS[attacker_phase], attacker_profile.eco.battle_cooldown)
        await redis.set(battle_cooldown(challenge.attacker_id), "1", ex=cd)
        await schedule_ready(redis, challenge.attacker_id, CD_BATTLE, cd)

    return ChallengeOutcome(
        **base,
        journal=journal(result, m.spy) + abs_lines,
        defender_journal=journal(result, m.spy, viewer_is_attacker=False) + abs_lines,
        district_number=district_number,
        resolution=resolution,
        attacker_won=result.attacker_won,
        captured=captured_districts > 0,
        captured_districts=captured_districts,
        attacker_promoted_to=promoted_to,
        free_attack=free_attack,
        throne=throne,
        liberations=liberations,
        rounds=result.rounds,
        attacker_quantity=result.attacker.initial_quantity,
        attacker_power=result.attacker.initial_power,
        attacker_dead=result.attacker.total_dead,
        attacker_fled=result.attacker.fled,
        defender_quantity=result.defender.initial_quantity,
        defender_power=result.defender.initial_power,
        defender_dead=result.defender.total_dead,
        defender_fled=result.defender.fled,
    )
