"""Задания систем развития — общий механизм (сервис).

Квест учителя уникальной техники, «подтверждение убеждений» и квест на путь
(`docs/design/development_systems.md`) устроены одинаково: набор заданий-действий в игре
(победы, тренировки, вербовка, боссы…) с целевым количеством. Сервисы игры сообщают о
событии через `emit()` — внутри своей транзакции, без commit, — и прогресс растёт у всех
активных квестов игрока, где есть это задание. Награду за выполненный квест выдаёт
домен-владелец (техника, убеждение, путь) — здесь только прогресс и закрытие.
"""
from __future__ import annotations

from datetime import datetime, timezone

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.unique_path import PATH_POINT_SOURCES
from bot.constant.unique_path import PATH_STAGE_OWNED
from bot.db.repositories import unique_path as path_repo

from bot.constant.dev_quest import QUEST_CONVICTION, QUEST_SCHOOL, QUEST_TEACHER, QUEST_TECH_LEVEL, STATUS_ACTIVE, TASK_WIN_PVE, TASK_WIN_PVP
from bot.db.models.dev_quest import DevQuest
from bot.db.repositories import battle_pass as bp_repo
from bot.db.repositories import dev_quest as quest_repo

# Свиток пропуска закрывает квесты учителей и убеждений; пробуждение — нет (это потолок силы).
SKIPPABLE_KINDS = frozenset({QUEST_CONVICTION, QUEST_TEACHER, QUEST_SCHOOL, QUEST_TECH_LEVEL})


@dataclass(frozen=True, slots=True)
class QuestView:
    id: int
    kind: str
    ref: str
    tasks: dict[str, int]
    progress: dict[str, int]

    @property
    def complete(self) -> bool:
        return all(self.progress.get(task, 0) >= need for task, need in self.tasks.items())


def view(quest: DevQuest) -> QuestView:
    return QuestView(quest.id, quest.kind, quest.ref, dict(quest.tasks), {k: int(v) for k, v in quest.progress.items()})


async def emit(session: AsyncSession, user_id: int, task: str, n: int = 1) -> None:
    """Событие игры → прогресс квестов, ежедневных заданий (`services/quest`) и очки пути (`award_path_points`). НЕ коммитит (шаг
    чужой транзакции)."""
    if n <= 0:
        return
    # Победа над игроком нападающим засчитывается и заданиям «победить ботов» (пользователь
    # 2026-10-28: «нельзя выполнить, если ботов нет — засчитывать бота ИЛИ игрока»).
    tasks = (task, TASK_WIN_PVE) if task == TASK_WIN_PVP else (task,)
    from bot.services.quest import on_event  # quest → battle_pass → dev_quest: ленивый импорт

    for t in tasks:
        await quest_repo.emit(session, user_id, t, n)
        await award_path_points(session, user_id, t)
        await on_event(session, user_id, t, n)


async def award_path_points(session: AsyncSession, user_id: int, source: str) -> int | None:
    """Очки пути за активность: источник из `PATH_POINT_SOURCES`, засчитывается не чаще своего
    интервала и только при пробуждённом пути. Одно событие — одно начисление, сколько бы штук
    оно ни включало (вербовка 1000 статистов = одна вербовка). НЕ коммитит."""
    spec = PATH_POINT_SOURCES.get(source)
    if spec is None:
        return None
    points, gate = spec
    # Путь тренировок: очки пути приходят быстрее на КПД тренировок.
    from bot.services.build import get_build

    kpd = (await get_build(session, user_id)).training_kpd
    if kpd:
        points = int(round(points * (1 + kpd)))
    return await path_repo.award_points(
        session, user_id, source, points, gate, PATH_STAGE_OWNED, int(datetime.now(timezone.utc).timestamp())
    )


async def start(session: AsyncSession, user_id: int, kind: str, ref: str, tasks: dict[str, int]) -> bool:
    """Начать квест (НЕ коммитит). False — такой уже идёт."""
    return await quest_repo.create(session, user_id, kind, ref, tasks)


async def list_active(session: AsyncSession, user_id: int, kind: str | None = None) -> list[QuestView]:
    return [view(q) for q in await quest_repo.list_active(session, user_id, kind)]


async def claim(session: AsyncSession, user_id: int, kind: str, ref: str = "") -> QuestView | None:
    """Закрыть выполненный квест под `FOR UPDATE` (двойной клик не выдаст награду дважды).
    → квест, если он выполнен и закрыт этим вызовом; None — нет/не выполнен. НЕ коммитит —
    домен-владелец выдаёт награду в той же транзакции и коммитит."""
    quest = await quest_repo.get_active_for_update(session, user_id, kind, ref)
    if quest is None:
        return None
    current = view(quest)
    if not current.complete or not await quest_repo.mark_done(session, quest.id):
        return None
    return current


class NoScrollError(Exception):
    pass


class QuestNotSkippableError(Exception):
    pass


async def skippable(session: AsyncSession, user_id: int) -> list[QuestView]:
    """Активные невыполненные квесты, которые закрывает свиток пропуска (Battle Pass)."""
    return [q for q in await list_active(session, user_id) if q.kind in SKIPPABLE_KINDS and not q.complete]


async def skip_with_scroll(session: AsyncSession, user_id: int, quest_id: int) -> QuestView:
    """Свиток пропуска: квест сразу выполнен (награду игрок забирает на экране домена, как
    обычно). Свиток списывается атомарно; квест — под `FOR UPDATE`. Коммитит."""
    quest = await session.scalar(
        select(DevQuest)
        .where(DevQuest.id == quest_id, DevQuest.user_id == user_id, DevQuest.status == STATUS_ACTIVE)
        .with_for_update()
    )
    if quest is None or quest.kind not in SKIPPABLE_KINDS or view(quest).complete:
        await session.rollback()
        raise QuestNotSkippableError
    if not await bp_repo.spend_skip_scroll(session, user_id):
        await session.rollback()
        raise NoScrollError
    quest.progress = dict(quest.tasks)
    result = view(quest)
    await session.commit()
    return result
