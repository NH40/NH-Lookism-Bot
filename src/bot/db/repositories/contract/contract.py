"""Контракты статистов — игрока (по лагерям) и клановой роты (репозиторий). Функции записи НЕ коммитят."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.clan import ClanContract
from bot.db.models.contract import StatistContract


async def list_active(
    session: AsyncSession, user_id: int, *, camp: str | None = None, for_update: bool = False
) -> Sequence[StatistContract]:
    """Действующие контракты игрока (все лагеря или один), раньше истекающие — первыми."""
    stmt = select(StatistContract).where(
        StatistContract.user_id == user_id, StatistContract.quantity > 0, StatistContract.expires_at > func.now()
    )
    if camp is not None:
        stmt = stmt.where(StatistContract.camp == camp)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt.order_by(StatistContract.expires_at, StatistContract.id))).all()


async def create(session: AsyncSession, user_id: int, rank: str, quantity: int, expires_at: datetime, camp: str = "attack") -> None:
    session.add(StatistContract(user_id=user_id, rank=rank, quantity=quantity, expires_at=expires_at, camp=camp))


async def move(session: AsyncSession, row: StatistContract, to_camp: str, count: int) -> None:
    """Перевести `count` бойцов контракта `row` в другой лагерь: весь контракт — сменой лагеря,
    часть — расщеплением (новая строка с тем же сроком). `row` уже под `FOR UPDATE`."""
    if count >= row.quantity:
        row.camp = to_camp
        return
    row.quantity -= count
    session.add(StatistContract(user_id=row.user_id, rank=row.rank, quantity=count, expires_at=row.expires_at, camp=to_camp))


async def lose(session: AsyncSession, contract_id: int, count: int) -> None:
    """Потери наёмников в бою."""
    await session.execute(
        update(StatistContract)
        .where(StatistContract.id == contract_id)
        .values(quantity=func.greatest(StatistContract.quantity - count, 0))
    )


async def purge(session: AsyncSession) -> None:
    """Истёкшие и выбитые контракты — игроков и клановых рот."""
    await session.execute(
        delete(StatistContract).where((StatistContract.expires_at <= func.now()) | (StatistContract.quantity <= 0))
    )
    await session.execute(delete(ClanContract).where((ClanContract.expires_at <= func.now()) | (ClanContract.quantity <= 0)))


async def delete_for_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(text("DELETE FROM statist_contracts WHERE user_id = :u"), {"u": user_id})


# --- клановая рота ---


async def list_clan_active(session: AsyncSession, clan_id: int, *, for_update: bool = False) -> Sequence[ClanContract]:
    stmt = select(ClanContract).where(ClanContract.clan_id == clan_id, ClanContract.quantity > 0, ClanContract.expires_at > func.now())
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt.order_by(ClanContract.expires_at, ClanContract.id))).all()


async def create_clan(session: AsyncSession, clan_id: int, rank: str, quantity: int, expires_at: datetime) -> None:
    session.add(ClanContract(clan_id=clan_id, rank=rank, quantity=quantity, expires_at=expires_at))


async def lose_clan(session: AsyncSession, contract_id: int, count: int) -> None:
    await session.execute(
        update(ClanContract).where(ClanContract.id == contract_id).values(quantity=func.greatest(ClanContract.quantity - count, 0))
    )
