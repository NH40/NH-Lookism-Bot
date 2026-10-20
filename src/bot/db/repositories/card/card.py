"""Уники игрока — стопки в армии по лагерям и позиции отряда (репозиторий).

Все функции записи НЕ коммитят: они шаги составных операций (крутка, перенос между
лагерями, постановка на позицию, потери в бою) — коммитит сервис (правило 10).
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.card_position import CardPosition
from bot.db.models.card_stack import CardStack


async def add_to_stack(session: AsyncSession, *, user_id: int, card_code: str, camp: str, quantity: int) -> None:
    """Атомарный upsert `quantity = quantity + :delta` (правило 1), delta любого знака —
    тот же приём, что `db/repositories/extra.add_to_stack`."""
    if quantity == 0:
        return
    await session.execute(
        pg_insert(CardStack)
        .values(user_id=user_id, card_code=card_code, camp=camp, quantity=quantity)
        .on_conflict_do_update(
            index_elements=[CardStack.user_id, CardStack.card_code, CardStack.camp],
            set_={"quantity": CardStack.quantity + quantity},
        )
    )


async def list_stacks(
    session: AsyncSession, user_id: int, *, camp: str | None = None, for_update: bool = False
) -> Sequence[CardStack]:
    stmt = select(CardStack).where(CardStack.user_id == user_id, CardStack.quantity > 0)
    if camp is not None:
        stmt = stmt.where(CardStack.camp == camp)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt)).all()


async def get_stack_for_update(session: AsyncSession, *, user_id: int, card_code: str, camp: str) -> CardStack | None:
    return await session.scalar(
        select(CardStack)
        .where(CardStack.user_id == user_id, CardStack.card_code == card_code, CardStack.camp == camp)
        .with_for_update()
    )


async def list_positions(session: AsyncSession, user_id: int) -> Sequence[CardPosition]:
    return (await session.scalars(select(CardPosition).where(CardPosition.user_id == user_id))).all()


async def get_position_for_update(session: AsyncSession, user_id: int, position: str) -> CardPosition | None:
    return await session.scalar(
        select(CardPosition)
        .where(CardPosition.user_id == user_id, CardPosition.position == position)
        .with_for_update()
    )


async def set_position(session: AsyncSession, user_id: int, position: str, card_code: str) -> None:
    await session.execute(
        pg_insert(CardPosition)
        .values(user_id=user_id, position=position, card_code=card_code)
        .on_conflict_do_update(
            index_elements=[CardPosition.user_id, CardPosition.position],
            set_={"card_code": card_code, "assigned_at": func.now()},
        )
    )


async def delete_position(session: AsyncSession, user_id: int, position: str) -> None:
    await session.execute(
        delete(CardPosition).where(CardPosition.user_id == user_id, CardPosition.position == position)
    )


async def count_copies(session: AsyncSession, user_id: int, card_code: str) -> int:
    """Всего копий карты у игрока: в армии (оба лагеря) + на позициях."""
    army = await session.scalar(
        select(func.coalesce(func.sum(CardStack.quantity), 0)).where(
            CardStack.user_id == user_id, CardStack.card_code == card_code
        )
    )
    placed = await session.scalar(
        select(func.count()).select_from(CardPosition).where(
            CardPosition.user_id == user_id, CardPosition.card_code == card_code
        )
    )
    return int(army) + int(placed)



async def add_many_to_stacks(session: AsyncSession, *, user_id: int, camp: str, quantities: dict[str, int]) -> None:
    """Пакетный `add_to_stack`: один INSERT ... ON CONFLICT на все карты сразу (массовое
    открытие тикетов). НЕ коммитит."""
    rows = [{"user_id": user_id, "card_code": code, "camp": camp, "quantity": q} for code, q in quantities.items() if q]
    if not rows:
        return
    stmt = pg_insert(CardStack).values(rows)
    await session.execute(stmt.on_conflict_do_update(
        index_elements=[CardStack.user_id, CardStack.card_code, CardStack.camp],
        set_={"quantity": CardStack.quantity + stmt.excluded.quantity},
    ))


async def owned_codes(session: AsyncSession, user_id: int, codes: list[str]) -> set[str]:
    """Какие из `codes` у игрока уже есть (в армии или на позициях) — двумя запросами."""
    if not codes:
        return set()
    army = await session.scalars(
        select(CardStack.card_code).where(CardStack.user_id == user_id, CardStack.card_code.in_(codes), CardStack.quantity > 0)
    )
    placed = await session.scalars(
        select(CardPosition.card_code).where(CardPosition.user_id == user_id, CardPosition.card_code.in_(codes))
    )
    return set(army) | set(placed)
