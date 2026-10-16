"""Журнал действий админов (сервис). `log` — шаг транзакции самого действия (НЕ коммитит):
если действие откатилось, записи о нём тоже не будет."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.admin import AdminAudit


async def log(
    session: AsyncSession, admin_id: int, action: str, target_id: int | None = None, details: dict | None = None
) -> None:
    session.add(AdminAudit(admin_id=admin_id, action=action, target_id=target_id, details=details or {}))
    await session.flush()


async def page(
    session: AsyncSession, *, target_id: int | None = None, admin_id: int | None = None, offset: int = 0, limit: int = 15
) -> tuple[list[AdminAudit], int]:
    """Записи журнала (новые сверху) с фильтром по игроку или админу. → (записи, всего)."""
    query = select(AdminAudit)
    count = select(func.count()).select_from(AdminAudit)
    if target_id is not None:
        query, count = query.where(AdminAudit.target_id == target_id), count.where(AdminAudit.target_id == target_id)
    if admin_id is not None:
        query, count = query.where(AdminAudit.admin_id == admin_id), count.where(AdminAudit.admin_id == admin_id)
    rows = (await session.execute(query.order_by(AdminAudit.id.desc()).offset(offset).limit(limit))).scalars().all()
    return list(rows), (await session.scalar(count)) or 0
