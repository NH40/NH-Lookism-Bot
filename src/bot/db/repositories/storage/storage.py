"""Ячейки хранения (репозиторий). Функции записи НЕ коммитят — коммитит сервис."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.storage_cell import StorageCell


async def list_cells(session: AsyncSession, user_id: int) -> Sequence[StorageCell]:
    return (await session.scalars(select(StorageCell).where(StorageCell.user_id == user_id).order_by(StorageCell.slot))).all()


async def get_for_update(session: AsyncSession, user_id: int, slot: int) -> StorageCell | None:
    return await session.scalar(
        select(StorageCell).where(StorageCell.user_id == user_id, StorageCell.slot == slot).with_for_update()
    )


async def create(session: AsyncSession, user_id: int, slot: int) -> bool:
    result = await session.execute(pg_insert(StorageCell).values(user_id=user_id, slot=slot).on_conflict_do_nothing())
    return result.rowcount > 0


async def put(session: AsyncSession, user_id: int, slot: int, kind: str, code: str, amount: int, fee_from: datetime) -> None:
    await session.execute(
        update(StorageCell)
        .where(StorageCell.user_id == user_id, StorageCell.slot == slot)
        .values(item_kind=kind, item_code=code, amount=amount, fee_from=fee_from)
    )


async def clear_contents(session: AsyncSession, user_id: int) -> None:
    """Сброс (пробуждение, удаление банды): вещи сгорают, купленные ячейки остаются."""
    await session.execute(
        text("UPDATE storage_cells SET item_kind = '', item_code = '', amount = 0 WHERE user_id = :uid"), {"uid": user_id}
    )
