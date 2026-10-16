"""Засчитать задания — инструмент тестирования и поддержки для админов (сервис).

Тестеры 2026-10-12: «кнопку, которая сразу выполняет все задания — тыкать вручную, чтобы
проверять, тяжело»; пользователь: «ещё в админ-панели после поиска игрока — засчитать игроку
одно задание или все». Себе — любой админ (кнопка на экране заданий), другому игроку — раздел
«Развитие» админки (уровень admin). Права перепроверяются здесь, не только видимостью кнопок.

Ежедневные задания засчитываются обычным путём событий (`services.quest.on_event`): опыт пасса,
множители порядка и бонус «все 10» — как у игрока. Квесты развития (учителя техник и школ,
убеждение, тренировка техники, пробуждение) получают полный прогресс — награду игрок забирает
на экране системы, как после свитка пропуска.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.constant.admin import SECTION_DEV
from bot.constant.dev_quest import STATUS_ACTIVE
from bot.db.models.dev_quest import DevQuest
from bot.db.repositories import quest as quest_repo
from bot.services.admin import audit, roles
from bot.services.admin.admin import is_admin
from bot.services.quest import on_event, today


class NotAdminError(Exception):
    pass


class QuestGoneError(Exception):
    """Задание уже выполнено или его нет."""


@dataclass(frozen=True, slots=True)
class OpenDaily:
    slot: int
    task: str
    progress: int
    target: int


@dataclass(frozen=True, slots=True)
class OpenDev:
    id: int
    kind: str
    ref: str


def _open_dev(quest: DevQuest) -> bool:
    return any(quest.progress.get(t, 0) < n for t, n in quest.tasks.items())


async def list_open(session: AsyncSession, user_id: int) -> tuple[list[OpenDaily], list[OpenDev]]:
    """Невыполненные задания игрока: ежедневные сегодня и активные квесты развития."""
    daily = [
        OpenDaily(q.slot, q.task, q.progress, q.target)
        for q in await quest_repo.list_day(session, user_id, today())
        if q.completed_at is None and q.target > q.progress
    ]
    rows = await session.scalars(
        select(DevQuest).where(DevQuest.user_id == user_id, DevQuest.status == STATUS_ACTIVE).order_by(DevQuest.created_at)
    )
    return daily, [OpenDev(q.id, q.kind, q.ref) for q in rows if _open_dev(q)]


async def _check(session: AsyncSession, admin_id: int, target_id: int) -> None:
    allowed = (
        await is_admin(session, admin_id, get_settings())
        if admin_id == target_id
        else await roles.can(session, admin_id, SECTION_DEV)
    )
    if not allowed:
        raise NotAdminError


async def complete(
    session: AsyncSession, admin_id: int, target_id: int, *, slot: int | None = None, dev_id: int | None = None
) -> tuple[int, int]:
    """Засчитать игроку `target_id`: одно ежедневное (`slot`), один квест развития (`dev_id`) или,
    если ничего не указано, — все невыполненные. → (ежедневных, квестов развития). Коммитит."""
    await _check(session, admin_id, target_id)
    one = slot is not None or dev_id is not None
    daily = dev = 0
    if not one or slot is not None:
        for q in await quest_repo.list_day(session, target_id, today()):
            if (slot is None or q.slot == slot) and q.completed_at is None and q.target > q.progress:
                await on_event(session, target_id, q.task, q.target - q.progress)
                daily += 1
    if not one or dev_id is not None:
        stmt = select(DevQuest).where(DevQuest.user_id == target_id, DevQuest.status == STATUS_ACTIVE)
        if dev_id is not None:
            stmt = stmt.where(DevQuest.id == dev_id)
        for quest in await session.scalars(stmt.with_for_update()):
            if _open_dev(quest):
                quest.progress = dict(quest.tasks)
                dev += 1
    if one and not (daily or dev):
        await session.rollback()
        raise QuestGoneError
    await audit.log(session, admin_id, "complete_quests", target_id, {"slot": slot, "dev_id": dev_id, "daily": daily, "dev": dev})
    await session.commit()
    return daily, dev


async def complete_all_quests(session: AsyncSession, admin_id: int) -> tuple[int, int]:
    """Тестовая кнопка на экране заданий: все свои задания разом."""
    return await complete(session, admin_id, admin_id)
