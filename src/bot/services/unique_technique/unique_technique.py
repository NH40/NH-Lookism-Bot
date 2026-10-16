"""Уникальные техники (сервис). Дизайн — `docs/design/development_systems.md`.

Пользователь 2026-10-02:
- на карте периодически появляются **учителя** (событие `teacher`, `services/event`), у
  каждого свой квест; игрок **коннектится** (или игнорирует) → квест
  (`services/dev_quest`) → выполнил → **получает технику учителя**;
- техник может быть несколько, **активна в бою одна** (свап не чаще
  `TECHNIQUE_SWAP_COOLDOWN_SECONDS`);
- уровни качаются **фрагментами УТ** с босса Джинена.

Родословная Ким Гапрена открывает технику Преодоления без учителя — `grant()` для неё.
Удаление банды техники стирает (`reset`) — их нет в списке сохраняемого пользователем.
"""
from __future__ import annotations

from bot.constant.donate import KIND_TECHNIQUE
from bot.db.repositories import donate as donate_repo

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import swap_cooldown
from bot.config.development import MAX_LEVEL
from bot.config.unique_technique import TEACHER_QUESTS, TECHNIQUE_SWAP_COOLDOWN_SECONDS, technique_level_cost
from bot.constant.activity import ACT_DEVELOPMENT
from bot.constant.dev_quest import QUEST_TECH_LEVEL, QUEST_TEACHER, TASK_DEV_LEVEL
from bot.constant.event import EVENT_TEACHER
from bot.constant.unique_technique import TECHNIQUES
from bot.db.repositories import dev_quest as quest_repo
from bot.db.repositories import event as event_repo
from bot.db.repositories import unique_technique as tech_repo
from bot.services.activity import log as log_activity
from bot.services.dev_quest import QuestView, claim, list_active, start
from bot.texts.activity import LOG_TECHNIQUE_LEVEL, LOG_TECHNIQUE_NEW
from bot.texts.unique_technique import TECHNIQUE_NAMES


class UnknownTechniqueError(Exception):
    pass


class TechniqueNotOwnedError(Exception):
    pass


class TechniqueOwnedError(Exception):
    """Техника этого учителя у игрока уже есть."""


class QuestAlreadyActiveError(Exception):
    pass


class QuestNotCompleteError(Exception):
    pass


class TrainingRequiredError(Exception):
    """Нет выполненной тренировки у учителя на этот уровень."""


class TeacherGoneError(Exception):
    pass


class TechniqueMaxLevelError(Exception):
    pass


class NotEnoughFragmentsError(Exception):
    def __init__(self, cost: int, have: int) -> None:
        super().__init__(cost, have)
        self.cost, self.have = cost, have


class SwapOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class TechniqueView:
    active: str | None
    owned: dict[str, int]
    fragments: int
    swap_cooldown: int
    next_costs: dict[str, int | None]
    quests: list[QuestView]


@dataclass(frozen=True, slots=True)
class TeacherView:
    event_id: int
    code: str
    owned: bool
    quest: QuestView | None
    ends_in_seconds: int



async def _swap_cd(session: AsyncSession, user_id: int, seconds: int) -> int:
    """КД переключения с мастерством Скорости («−10/20/30% ко ВСЕМ КД», raw-notes; до 2026-10-12
    переключения его не учитывали)."""
    from bot.services.characteristic import get_combat_profile

    return (await get_combat_profile(session, user_id)).cooldown(seconds)

async def get_view(session: AsyncSession, redis: Redis, user_id: int) -> TechniqueView:
    owned = dict(await tech_repo.list_owned(session, user_id))
    active, fragments = await tech_repo.get_state(session, user_id)
    return TechniqueView(
        active=active,
        owned=owned,
        fragments=fragments,
        swap_cooldown=max(0, await redis.ttl(swap_cooldown(user_id, "technique"))),
        next_costs={c: technique_level_cost(lv + 1) if lv < MAX_LEVEL else None for c, lv in owned.items()},
        quests=await list_active(session, user_id, QUEST_TEACHER),
    )


async def get_teacher(session: AsyncSession, user_id: int, event_id: int) -> TeacherView:
    event = await event_repo.get_active(session, event_id, user_id)
    if event is None or event.kind != EVENT_TEACHER:
        raise TeacherGoneError
    owned = dict(await tech_repo.list_owned(session, user_id))
    quests = {q.ref: q for q in await list_active(session, user_id, QUEST_TEACHER)}
    return TeacherView(
        event_id=event.id,
        code=event.code,
        owned=event.code in owned,
        quest=quests.get(event.code),
        ends_in_seconds=max(0, int((event.ends_at - datetime.now(timezone.utc)).total_seconds())),
    )


async def connect(session: AsyncSession, user_id: int, event_id: int) -> QuestView:
    """«Законнектиться» с учителем на карте — его квест. Коммитит."""
    event = await event_repo.get_active(session, event_id, user_id)
    if event is None or event.kind != EVENT_TEACHER:
        raise TeacherGoneError
    entry = await event_repo.lock_entry(session, event_id, user_id)
    owned = dict(await tech_repo.list_owned(session, user_id))
    if event.code in owned:
        raise TechniqueOwnedError
    if not await start(session, user_id, QUEST_TEACHER, event.code, TEACHER_QUESTS[event.code]):
        raise QuestAlreadyActiveError
    entry.connected = True
    await session.commit()
    quests = {q.ref: q for q in await list_active(session, user_id, QUEST_TEACHER)}
    return quests[event.code]


async def grant(session: AsyncSession, user_id: int, code: str) -> bool:
    """Выдать технику (квест учителя выполнен, родословная Гапрена). Первая — сразу активна.
    НЕ коммитит. → False — уже была."""
    if not await tech_repo.add(session, user_id, code):
        return False
    # Купленный за донат уровень — сразу (пол уровня переживает сброс, `services/donate`).
    if level := await donate_repo.floor(session, user_id, KIND_TECHNIQUE, code):
        await donate_repo.raise_owned_level(session, user_id, KIND_TECHNIQUE, code, level)
    await tech_repo.set_active_if_missing(session, user_id, code)
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_TECHNIQUE_NEW.format(name=TECHNIQUE_NAMES[code]))
    return True


async def claim_teacher_quest(session: AsyncSession, user_id: int, code: str) -> None:
    """Выполненный квест учителя → его техника. Коммитит."""
    if code not in TECHNIQUES:
        raise UnknownTechniqueError(code)
    if await claim(session, user_id, QUEST_TEACHER, code) is None:
        raise QuestNotCompleteError
    await grant(session, user_id, code)
    await session.commit()


async def activate(session: AsyncSession, redis: Redis, user_id: int, code: str) -> None:
    owned = dict(await tech_repo.list_owned(session, user_id))
    if code not in owned:
        raise TechniqueNotOwnedError
    key = swap_cooldown(user_id, "technique")
    if not await redis.set(key, "1", nx=True, ex=await _swap_cd(session, user_id, TECHNIQUE_SWAP_COOLDOWN_SECONDS)):
        raise SwapOnCooldownError(max(0, await redis.ttl(key)))
    await tech_repo.set_active(session, user_id, code)
    await session.commit()


async def level_up(session: AsyncSession, user_id: int, code: str) -> int:
    owned = dict(await tech_repo.list_owned(session, user_id))
    if code not in owned:
        raise TechniqueNotOwnedError
    current = owned[code]
    if current >= MAX_LEVEL:
        raise TechniqueMaxLevelError
    cost = technique_level_cost(current + 1)
    # Уровень открывает только выполненная тренировка у учителя техники (2026-10-12):
    # квест закрывается под `FOR UPDATE` в той же транзакции, что списание фрагментов.
    if await claim(session, user_id, QUEST_TECH_LEVEL, f"{code}:{current + 1}") is None:
        raise TrainingRequiredError
    if not await tech_repo.spend_fragments(session, user_id, cost):
        await session.rollback()
        _, have = await tech_repo.get_state(session, user_id)
        raise NotEnoughFragmentsError(cost, have)
    if not await tech_repo.bump_level(session, user_id, code, current):
        await session.rollback()
        raise TechniqueMaxLevelError
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_TECHNIQUE_LEVEL.format(name=TECHNIQUE_NAMES[code], level=current + 1))
    await quest_event(session, user_id, TASK_DEV_LEVEL)
    await session.commit()
    return current + 1


async def reset(session: AsyncSession, user_id: int) -> None:
    """Удаление банды: техники и квесты учителей стираются. НЕ коммитит."""
    await tech_repo.delete_all(session, user_id)
    await quest_repo.delete_for_user(session, user_id, (QUEST_TEACHER,))
