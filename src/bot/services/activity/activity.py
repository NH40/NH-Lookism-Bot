"""Журнал действий игроков и память противников (сервис).

`log()` вызывают сервисы боёв, захватов, построек и развития — внутри их транзакции, без
своего commit. Читают журнал разведка (гений наблюдения) и метки (путь Сенсорики) —
`services/intel`. `remember_opponents()` — после PvP-боя: оба запоминают путь друг друга
(пути Копирования и Бесконечной техники берут способности последних противников).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.activity import ACTIVITY_KEEP_DAYS
from bot.config.development import PATH_MEMORY_SIZE
from bot.db.repositories import activity as activity_repo


async def log(session: AsyncSession, user_id: int, kind: str, line: str) -> None:
    await activity_repo.add(session, user_id, kind, line)


async def remember_opponents(session: AsyncSession, a_id: int, b_id: int) -> None:
    """Каждый запоминает активный путь другого (если он есть). НЕ коммитит."""
    for me, other in ((a_id, b_id), (b_id, a_id)):
        path = await activity_repo.active_path(session, other)
        if path is not None:
            await activity_repo.remember(session, me, other, path, PATH_MEMORY_SIZE)


async def purge(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await activity_repo.purge(session, ACTIVITY_KEEP_DAYS)
        await session.commit()
