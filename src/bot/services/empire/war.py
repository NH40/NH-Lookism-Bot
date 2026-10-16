"""Война императоров — вызов, бой, переход городов и казны (сервис).

Пользователь (`docs/design/fist_emperor.md` + AskUserQuestion 2026-10-02):
- император атакует другого императора — **вызов с окном принятия**: принял — бой, не
  принял до срока — **проиграл без боя**;
- победивший нападающий отбивает **случайные** города проигравшего; игроки в них платят
  новому императору по его правилам; сколько городов — от перевеса мощи;
- победитель забирает **10–50% казны** (кошелька NHCoin) проигравшего: большая разница в
  мощи — 10%, максимально близкая — 50%;
- император, потерявший **все** города, — **в банду** (как проигравший бой за трон).

Решения автора кода (записаны в CLAUDE.md): бой при принятии — лагерь атаки против лагеря
атаки (как PvP-вызов); при неявке перевес считается по тем же лагерям без боя; победивший
защитник забирает только долю казны нападающего — города отбивает лишь нападающий.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.services.absolute import after_battle
from bot.services.intel.scout import has_report as has_scout_report
from bot.constant.position_skill import ROLE_ATTACK, ROLE_DEFENSE, VS_WAR
from bot.services.position_skill.battle import journal, matchup
from bot.cache.keys import empire_war_cooldown, empire_war_shield
from bot.config.empire import (
    EMPIRE_WAR_ACCEPT_SECONDS,
    EMPIRE_WAR_COOLDOWN_SECONDS,
    EMPIRE_WAR_SHIELD_SECONDS,
    EMPIRE_WAR_SWEEP_BATCH,
    EMPIRE_WAR_HISTORY_SHOWN,
    EMPIRE_WAR_TARGETS_PAGE_SIZE,
    war_cities,
    war_treasury_percent,
)
from bot.constant.empire import WAR_ACCEPTED, WAR_FORFEIT, WAR_VOID
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.db.repositories import phase as phase_repo
from bot.db.repositories import empire as empire_repo
from bot.db.repositories.empire import EmperorRow
from bot.db.repositories.phase import get_phase
from bot.constant.activity import ACT_BATTLE
from bot.services.activity import log as log_activity
from bot.services.activity import remember_opponents
from bot.constant.dev_quest import TASK_WAR_WIN, TASK_WIN_PVP
from bot.services.dev_quest import emit as quest_event
from bot.services.stealth import label as stealth_label
from bot.texts.activity import LOG_WAR_ATTACKER, LOG_WAR_DEFENDER, LOST, WON
from bot.services.business import accrue_many
from bot.services.characteristic import get_combat_profile
from bot.services.combat import simulate_battle
from bot.services.district import NoAttackersError
from bot.services.district.army import apply_losses, load_camp
from bot.services.gang import get_gang
from bot.services.phase import demote_to_gang, is_emperor

log = logging.getLogger(__name__)

_NO_ARMY_RATIO = 1_000_000.0


class NotEmperorError(Exception):
    pass


class TargetNotEmperorError(Exception):
    pass


class TargetHasNoCitiesError(Exception):
    pass


class TargetShieldedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class WarOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class OutgoingWarExistsError(Exception):
    pass


class TargetAtWarError(Exception):
    """На цель уже висит чужой вызов."""


class WarNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TargetsPage:
    items: list[EmperorRow]
    page: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class WarIssued:
    war_id: int
    attacker_id: int
    defender_id: int
    attacker_label: str
    window_seconds: int


@dataclass(frozen=True, slots=True)
class WarOutcome:
    war_id: int
    attacker_id: int
    defender_id: int
    attacker_label: str
    defender_label: str
    resolution: str
    attacker_won: bool = False
    rounds: int = 0
    attacker_power: int = 0
    attacker_dead: int = 0
    defender_power: int = 0
    defender_dead: int = 0
    city_names: list[str] = field(default_factory=list)
    treasury_taken: int = 0
    treasury_percent: int = 0
    defender_demoted: bool = False
    businesses_taken: int = 0  # зданий из владений перешло победителю вместе с городами
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)
    defender_journal: tuple[str, ...] = ()  # тот же бой глазами защитника


async def _ensure_emperor(session: AsyncSession, user_id: int) -> None:
    current = await get_phase(session, user_id)
    if current is None or not is_emperor(current[0]):
        raise NotEmperorError


async def _label(session: AsyncSession, user_id: int) -> str:
    gang = await get_gang(session, user_id)
    return await stealth_label(session, user_id, gang.name if gang else "—")


async def list_targets(session: AsyncSession, user_id: int, page: int) -> TargetsPage:
    await _ensure_emperor(session, user_id)
    page = max(page, 0)
    items, has_more = await empire_repo.list_emperors(
        session, exclude_id=user_id, offset=page * EMPIRE_WAR_TARGETS_PAGE_SIZE, limit=EMPIRE_WAR_TARGETS_PAGE_SIZE
    )
    return TargetsPage(items=items, page=page, has_more=has_more)


async def get_target(session: AsyncSession, user_id: int, target_id: int) -> EmperorRow:
    await _ensure_emperor(session, user_id)
    target = await empire_repo.get_emperor(session, target_id)
    if target is None or target_id == user_id:
        raise TargetNotEmperorError
    return target


async def declare_war(session: AsyncSession, redis: Redis, attacker_id: int, defender_id: int) -> WarIssued:
    """Объявление войны. Порядок: права → цель → щит цели → висящие вызовы → КД (`SET NX EX`,
    он же защита от двойного клика) → строка вызова (частичные уникальные индексы — вторая
    линия защиты от гонки) → commit. Сбой после взятия КД — КД снимается."""
    target = await get_target(session, attacker_id, defender_id)
    if target.cities == 0:
        raise TargetHasNoCitiesError
    shield = await redis.ttl(empire_war_shield(defender_id))
    if shield > 0:
        raise TargetShieldedError(shield)
    # Без лагеря атаки воевать нечем — иначе при неявке защитника пустая армия «победила» бы.
    if not await load_camp(session, attacker_id, CAMP_ATTACK, for_update=False):
        raise NoAttackersError
    if await empire_repo.has_pending_as_attacker(session, attacker_id):
        raise OutgoingWarExistsError
    if await empire_repo.has_pending_as_defender(session, defender_id):
        raise TargetAtWarError

    profile = await get_combat_profile(session, attacker_id)
    key = empire_war_cooldown(attacker_id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(EMPIRE_WAR_COOLDOWN_SECONDS)):
        raise WarOnCooldownError(max(0, await redis.ttl(key)))
    window = profile.accept_window(EMPIRE_WAR_ACCEPT_SECONDS)
    try:
        war_id = await empire_repo.create_war(
            session, attacker_id=attacker_id, defender_id=defender_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=window),
        )
        label = await _label(session, attacker_id)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await redis.delete(key)
        raise TargetAtWarError from None
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return WarIssued(war_id=war_id, attacker_id=attacker_id, defender_id=defender_id, attacker_label=label,
                     window_seconds=window)


async def war_history(session: AsyncSession, user_id: int) -> list[empire_repo.WarHistoryRow]:
    """Последние завершённые войны императора — для экрана империи в Mini App."""
    return await empire_repo.list_war_history(session, user_id, EMPIRE_WAR_HISTORY_SHOWN)


async def get_incoming(session: AsyncSession, defender_id: int):
    """Висящая война против императора (для экрана империи) — или None."""
    return await empire_repo.get_incoming(session, defender_id)


async def accept_war(session: AsyncSession, redis: Redis, defender_id: int, war_id: int) -> WarOutcome:
    """«Принять бой». Нажатие после срока, но до sweep — неявка (как у PvP-вызовов)."""
    war = await empire_repo.get_pending_for_update(session, war_id)
    if war is None or war.defender_id != defender_id:
        raise WarNotFoundError
    expired = datetime.now(timezone.utc) >= war.expires_at
    return await _resolve(session, redis, war, WAR_FORFEIT if expired else WAR_ACCEPTED)


async def resolve_expired(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> list[WarOutcome]:
    """Фоновый проход: неявка защитника — поражение без боя. Каждая война — своя
    транзакция, падение одной не мешает остальным."""
    async with session_factory() as session:
        ids = await empire_repo.list_expired_war_ids(session, EMPIRE_WAR_SWEEP_BATCH)
    outcomes = []
    for war_id in ids:
        async with session_factory() as session:
            try:
                war = await empire_repo.get_pending_for_update(session, war_id)
                if war is not None:
                    outcomes.append(await _resolve(session, redis, war, WAR_FORFEIT))
            except Exception:
                await session.rollback()
                log.exception("Failed to resolve expired emperor war %s", war_id)
    return outcomes


def _camp_power(camp) -> int:
    return int(sum(s.unit_power * s.quantity for s in camp))


async def _resolve(session: AsyncSession, redis: Redis, war, resolution: str, *, rng: random.Random | None = None) -> WarOutcome:
    rng = rng or random.Random()
    attacker_id, defender_id = war.attacker_id, war.defender_id
    labels = {"attacker_label": await _label(session, attacker_id), "defender_label": await _label(session, defender_id)}

    # К моменту боя оба должны остаться императорами, а у защитника — города.
    attacker_phase, defender_phase = await get_phase(session, attacker_id), await get_phase(session, defender_id)
    if (
        attacker_phase is None or not is_emperor(attacker_phase[0])
        or defender_phase is None or not is_emperor(defender_phase[0])
        or await empire_repo.count_cities(session, defender_id) == 0
    ):
        await empire_repo.finish_war(session, war.id, resolution=WAR_VOID, attacker_won=None)
        await session.commit()
        return WarOutcome(war.id, attacker_id, defender_id, resolution=WAR_VOID, **labels)

    rounds = attacker_dead = defender_dead = 0
    war_journal: tuple[str, ...] = ()
    war_journal_def: tuple[str, ...] = ()
    if resolution in (WAR_ACCEPTED, WAR_FORFEIT):
        # Принял — лагеря атаки обеих сторон; не принял — автобой: бьётся лагерь защиты защитника
        # (баланс 2026-10-16: 5 из 8 войн решала неявка, вместе с казной ушло ~920 млрд).
        defender_camp = CAMP_ATTACK if resolution == WAR_ACCEPTED else CAMP_DEFENSE
        # Стопки — в порядке user_id (как в PvP), чтобы встречные бои не упёрлись в дедлок.
        sides = {attacker_id: CAMP_ATTACK, defender_id: defender_camp}
        camps = {uid: await load_camp(session, uid, sides[uid], for_update=True) for uid in sorted(sides)}
        m = matchup(
            await get_combat_profile(session, attacker_id), await get_combat_profile(session, defender_id),
            vs=(VS_WAR,), defender_role=ROLE_ATTACK if resolution == WAR_ACCEPTED else ROLE_DEFENSE, rng=rng,
            scouted=await has_scout_report(session, attacker_id, defender_id),
            attacker_stacks=camps[attacker_id], defender_stacks=camps[defender_id],
        )
        result = simulate_battle(
            camps[attacker_id], camps[defender_id], attacker_chances=m.attacker, defender_chances=m.defender, rng=rng,
        )
        abs_lines = await after_battle(session, m, result, attacker_id=attacker_id, attacker_stacks=camps[attacker_id], defender_id=defender_id)
        war_journal = journal(result, m.spy) + abs_lines
        war_journal_def = journal(result, m.spy, viewer_is_attacker=False) + abs_lines
        await apply_losses(session, attacker_id, CAMP_ATTACK, result.attacker.dead)
        await apply_losses(session, defender_id, defender_camp, result.defender.dead)
        attacker_won = result.attacker_won
        attacker_power, defender_power = result.attacker.initial_power, result.defender.initial_power
        rounds, attacker_dead, defender_dead = result.rounds, result.attacker.total_dead, result.defender.total_dead

    winner, loser = (attacker_id, defender_id) if attacker_won else (defender_id, attacker_id)
    winner_power, loser_power = (attacker_power, defender_power) if attacker_won else (defender_power, attacker_power)
    # Проигравший без армии — «бесконечный» перевес; конечное число, чтобы формулы не
    # падали на int(inf) (города всё равно обрежутся числом городов проигравшего).
    ratio = winner_power / loser_power if loser_power > 0 else _NO_ARMY_RATIO

    # Казна проигравшего — под FOR UPDATE, доля от перевеса.
    percent = war_treasury_percent(ratio)
    loser_coins = await empire_repo.emperor_coins(session, loser, for_update=True)
    treasury = loser_coins * percent // 100
    if treasury:
        await empire_repo.move_coins(session, loser, winner, treasury)

    names: list[str] = []
    demoted = False
    businesses = 0
    if attacker_won:
        cities = await empire_repo.city_ids_for_update(session, defender_id)
        taken = rng.sample(cities, min(war_cities(ratio), len(cities)))
        # Доход жителей до смены императора не трогаем: налог берётся в момент зачисления
        # (см. налоги) — новые правила действуют со следующего зачисления.
        await empire_repo.transfer_cities(session, taken, from_id=defender_id, to_id=attacker_id)
        names = await empire_repo.city_names(session, taken)
        # Владения уходят вместе с городами (пользователь 2026-10-14: «бизнесы проигравшего тоже
        # переходят — деньги меняются в зависимости от войны»): здания из потерянных городов +
        # доля старых без города; потерял последние города — уходит всё. Доход обоим — до этой секунды.
        await accrue_many(session, [attacker_id, defender_id])
        final = len(taken) == len(cities)
        businesses = await phase_repo.transfer_holdings(
            session, defender_id, attacker_id, taken, len(cities), everything=final
        )
        if final:
            # Без городов и бизнесов — в банду (пользователь).
            await demote_to_gang(session, defender_id)
            demoted = True

    await empire_repo.finish_war(
        session, war.id, resolution=resolution, attacker_won=attacker_won,
        cities_taken=len(names), treasury_taken=treasury,
    )
    await log_activity(
        session, attacker_id, ACT_BATTLE,
        LOG_WAR_ATTACKER.format(defender=labels["defender_label"], outcome=WON if attacker_won else LOST, cities=len(names)),
    )
    await log_activity(
        session, defender_id, ACT_BATTLE,
        LOG_WAR_DEFENDER.format(attacker=labels["attacker_label"], outcome=LOST if attacker_won else WON, cities=len(names)),
    )
    if resolution == WAR_ACCEPTED:
        await remember_opponents(session, attacker_id, defender_id)
    # Квест кулака на пробуждение: победа в войне императоров.
    await quest_event(session, winner, TASK_WAR_WIN)
    if attacker_won and resolution == WAR_ACCEPTED:
        # Аналог для императора (пользователь 2026-10-12): районов для PvP-вызова у него нет, поэтому
        # победа нападающим в войне императоров засчитывается заданиям «победить игрока нападающим»
        # и этапу 3 мастерства (в т.ч. «победа над равным» по мощи лагерей).
        await quest_event(session, attacker_id, TASK_WIN_PVP)
        from bot.services.mastery import record_pvp_win

        await record_pvp_win(session, attacker_id, attacker_power, defender_power)
    await session.commit()
    # Щит защитнику — только после commit (правило 10: Redis не опережает Postgres).
    await redis.set(empire_war_shield(defender_id), "1", ex=EMPIRE_WAR_SHIELD_SECONDS)
    return WarOutcome(
        war.id, attacker_id, defender_id, resolution=resolution, attacker_won=attacker_won, rounds=rounds,
        journal=war_journal, defender_journal=war_journal_def,
        attacker_power=int(attacker_power), attacker_dead=attacker_dead,
        defender_power=int(defender_power), defender_dead=defender_dead,
        city_names=names, treasury_taken=treasury, treasury_percent=percent, defender_demoted=demoted,
        businesses_taken=businesses, **labels,
    )
