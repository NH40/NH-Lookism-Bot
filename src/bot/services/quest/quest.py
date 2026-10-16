"""Ежедневные задания (сервис). Дизайн — `config/quest` (пользователь 2026-10-04): 10 заданий
в день из пула 100, раз в день — либо полный реролл невыполненных, либо до 2 замен по одному;
выполненное задание сразу даёт опыт Battle Pass (первое за день ×3, второе ×2), все 10 — бонус.

Набор дня создаётся лениво — при открытии экрана или первом событии игры за день (по Москве).
Прогресс растёт от тех же событий, что и задания развития (`services/dev_quest.emit` →
`on_event`), внутри транзакции действия игрока, без своего commit.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.battle_pass import BP_ALL_DONE_XP, BP_QUEST_ORDER_MULTIPLIERS
from bot.config.game import ACTION_LOCK_MS
from bot.config.quest import (
    QUEST_DAY_TZ,
    QUEST_NEEDS_CLAN,
    QUEST_NEEDS_SCHOOL,
    QUEST_POOL,
    QUEST_REPEAT_DAYS,
    QUEST_SWAPS_PER_DAY,
    QUEST_TARGETS,
    QUEST_TIER_WEIGHTS,
    QUESTS_PER_DAY,
    quest_code,
)
from bot.constant.quest import LOCK_ACTION_QUEST
from bot.db.models.quest import DailyQuest, DailyQuestState
from bot.db.repositories import quest as quest_repo
from bot.services.battle_pass import add_xp


class QuestBusyError(Exception):
    pass


class RerollUsedError(Exception):
    """Реролл дня уже потрачен (полный или замены — взаимоисключающие)."""


class QuestAlreadyDoneError(Exception):
    pass


class QuestNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DailyQuestView:
    slot: int
    task: str
    target: int
    tier: int
    xp: int
    progress: int
    done: bool


@dataclass(frozen=True, slots=True)
class QuestStatus:
    quests: list[DailyQuestView]
    completed: int
    full_reroll_available: bool
    swaps_left: int
    next_multiplier: int  # множитель опыта для следующего выполненного задания
    resets_in: int  # секунд до нового набора


def today() -> date:
    return datetime.now(QUEST_DAY_TZ).date()


def order_multiplier(order: int) -> int:
    """Множитель опыта для `order`-го выполненного за день задания (1-based)."""
    return BP_QUEST_ORDER_MULTIPLIERS[order - 1] if 0 < order <= len(BP_QUEST_ORDER_MULTIPLIERS) else 1


def _seconds_to_midnight() -> int:
    now = datetime.now(QUEST_DAY_TZ)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), QUEST_DAY_TZ)
    return int((midnight - now).total_seconds())


async def _unavailable_tasks(session: AsyncSession, user_id: int) -> set[str]:
    in_clan, has_school = (
        await session.execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM clan_members WHERE user_id = :u), "
                "EXISTS(SELECT 1 FROM user_schools WHERE user_id = :u AND owned)"
            ),
            {"u": user_id},
        )
    ).one()
    blocked: set[str] = set()
    if not in_clan:
        blocked |= QUEST_NEEDS_CLAN
    if not has_school:
        blocked |= QUEST_NEEDS_SCHOOL
    return blocked


def _pick(
    k: int, blocked: set[str], avoid_tasks: set[str], avoid_codes: set[str], rng: random.Random
) -> list[tuple[str, str, int, int]]:
    """k заданий разных видов: (код, событие, цель, опыт). Сначала без недавних видов/кодов,
    при нехватке — ослабляем ограничения (но вид в одном дне не повторяется никогда)."""
    tasks = [t for t in QUEST_TARGETS if t not in blocked and t not in avoid_tasks]
    rng.shuffle(tasks)
    picked: list[tuple[str, str, int, int]] = []
    for task in tasks:
        if len(picked) == k:
            break
        tiers = [tier for tier in range(4) if quest_code(task, tier) not in avoid_codes] or list(range(4))
        tier = rng.choices(tiers, weights=[QUEST_TIER_WEIGHTS[t] for t in tiers])[0]
        code = quest_code(task, tier)
        _, target, _, xp = QUEST_POOL[code]
        picked.append((code, task, target, xp))
    return picked


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_QUEST)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise QuestBusyError
    return key


async def _ensure_day(session: AsyncSession, user_id: int, day: date) -> tuple[DailyQuestState, list[DailyQuest]]:
    """Состояние и набор дня под `FOR UPDATE` состояния; новый день — сброс и новые 10 заданий.
    НЕ коммитит."""
    state = await quest_repo.lock_state(session, user_id, day)
    quests = list(await quest_repo.list_day(session, user_id, day))
    if state.day == day and quests:
        return state, quests
    state.day, state.full_reroll_used, state.swaps_used, state.completed = day, False, 0, 0
    since = day - timedelta(days=QUEST_REPEAT_DAYS)
    await quest_repo.purge_before(session, user_id, since)
    recent = await quest_repo.codes_since(session, user_id, since)
    picked = _pick(QUESTS_PER_DAY, await _unavailable_tasks(session, user_id), set(), recent, random.Random())
    await quest_repo.insert(
        session, user_id, day, [(slot, code, task, target, xp) for slot, (code, task, target, xp) in enumerate(picked, 1)]
    )
    return state, list(await quest_repo.list_day(session, user_id, day))


def _status(state: DailyQuestState, quests: list[DailyQuest]) -> QuestStatus:
    views = [
        DailyQuestView(q.slot, q.task, q.target, QUEST_POOL[q.code][2], q.xp, q.progress, q.completed_at is not None)
        for q in quests
    ]
    return QuestStatus(
        views,
        state.completed,
        not state.full_reroll_used and state.swaps_used == 0,
        0 if state.full_reroll_used else QUEST_SWAPS_PER_DAY - state.swaps_used,
        order_multiplier(state.completed + 1),
        _seconds_to_midnight(),
    )


async def get_status(session: AsyncSession, user_id: int) -> QuestStatus:
    """Экран заданий: при необходимости создаёт набор дня и коммитит его."""
    state, quests = await _ensure_day(session, user_id, today())
    status = _status(state, quests)
    await session.commit()
    return status


async def on_event(session: AsyncSession, user_id: int, task: str, n: int) -> None:
    """Событие игры → прогресс заданий дня; выполненные сразу дают опыт пасса. НЕ коммитит."""
    if task not in QUEST_TARGETS or n <= 0:
        return
    day = today()
    if await quest_repo.state_day(session, user_id) != day:
        await _ensure_day(session, user_id, day)
    done = await quest_repo.advance(session, user_id, day, task, n)
    if not done:
        return
    count = await quest_repo.add_completed(session, user_id, len(done))
    first = count - len(done) + 1
    xp = sum(quest_xp * order_multiplier(first + i) for i, (_, quest_xp) in enumerate(done))
    if count >= QUESTS_PER_DAY > count - len(done):
        xp += BP_ALL_DONE_XP
    await add_xp(session, user_id, xp)


async def reroll_all(session: AsyncSession, redis: Redis, user_id: int) -> QuestStatus:
    """Полный реролл: все невыполненные задания дня — новые, других видов. Раз в день, вместо замен."""
    key = await _lock(redis, user_id)
    try:
        day = today()
        state, quests = await _ensure_day(session, user_id, day)
        if state.full_reroll_used or state.swaps_used:
            raise RerollUsedError
        open_slots = [q.slot for q in quests if q.completed_at is None]
        if open_slots:
            await _replace(session, user_id, day, quests, open_slots)
        state.full_reroll_used = True
        status = _status(state, list(await quest_repo.list_day(session, user_id, day)))
        await session.commit()
        return status
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def swap(session: AsyncSession, redis: Redis, user_id: int, slot: int) -> QuestStatus:
    """Замена одного невыполненного задания (до `QUEST_SWAPS_PER_DAY` в день, вместо полного реролла)."""
    key = await _lock(redis, user_id)
    try:
        day = today()
        state, quests = await _ensure_day(session, user_id, day)
        if state.full_reroll_used or state.swaps_used >= QUEST_SWAPS_PER_DAY:
            raise RerollUsedError
        quest = next((q for q in quests if q.slot == slot), None)
        if quest is None:
            raise QuestNotFoundError
        if quest.completed_at is not None:
            raise QuestAlreadyDoneError
        await _replace(session, user_id, day, quests, [slot])
        state.swaps_used += 1
        status = _status(state, list(await quest_repo.list_day(session, user_id, day)))
        await session.commit()
        return status
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def _replace(session: AsyncSession, user_id: int, day: date, quests: list[DailyQuest], slots: list[int]) -> None:
    since = day - timedelta(days=QUEST_REPEAT_DAYS)
    blocked = await _unavailable_tasks(session, user_id)
    day_tasks = {q.task for q in quests}
    kept_tasks = {q.task for q in quests if q.slot not in slots}
    recent = await quest_repo.codes_since(session, user_id, since)
    rng = random.Random()
    picked = _pick(len(slots), blocked, day_tasks, recent, rng)
    if len(picked) < len(slots):  # мало видов — разрешаем вернуть заменяемые виды
        picked += _pick(len(slots) - len(picked), blocked, kept_tasks | {p[1] for p in picked}, recent, rng)
    await quest_repo.delete_slots(session, user_id, day, slots)
    await session.flush()
    await quest_repo.insert(
        session, user_id, day, [(slot, code, task, target, xp) for slot, (code, task, target, xp) in zip(slots, picked)]
    )

