"""Ресурсы игрока (сервис) — единая точка «сколько есть / списать / начислить» для биржи,
казино, ячеек хранения и вкладов.

Все функции записи — атомарные одиночные UPDATE (правило 1: `WHERE колонка >= :amount`) и
НЕ коммитят: это шаги составных операций (лот биржи, ставка, вклад), коммит — у
вызывающего сервиса (правило 10). Тикеты идут через `services/ticket` — у них ленивый реген:
перед начислением реген фиксируется (списание 0), иначе начисление поверх потолка сдвинуло
бы таймер регена.
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.resource import (
    RES_BLOOD,
    RES_DONATE,
    RES_COINS,
    RES_DEV_POINTS,
    RES_GENIUS_FRAGMENTS,
    RES_PATH_FRAGMENTS,
    RES_PATH_POINTS,
    RES_TECHNIQUE_FRAGMENTS,
    RES_TICKETS,
    RESOURCES,
)
from bot.db.models.user import User
from bot.services import ticket as ticket_service


class UnknownResourceError(Exception):
    pass


# Ресурс → колонка `users` (тикеты — отдельно, через `services/ticket`).
_COLUMNS = {
    RES_COINS: User.nh_coins,
    RES_DEV_POINTS: User.dev_points,
    RES_PATH_POINTS: User.path_points,
    RES_PATH_FRAGMENTS: User.path_fragments,
    RES_TECHNIQUE_FRAGMENTS: User.technique_fragments,
    RES_GENIUS_FRAGMENTS: User.genius_fragments,
    RES_BLOOD: User.blood_drops,
    RES_DONATE: User.donate_coins,
}


def _check(code: str) -> None:
    if code not in RESOURCES:
        raise UnknownResourceError(code)


async def balance(session: AsyncSession, user_id: int, code: str) -> int:
    _check(code)
    if code == RES_TICKETS:
        return (await ticket_service.get_status(session, user_id)).count
    return int(await session.scalar(select(_COLUMNS[code]).where(User.id == user_id)) or 0)


async def balances(session: AsyncSession, user_id: int) -> dict[str, int]:
    """Все ресурсы игрока одним запросом (плюс тикеты с регеном)."""
    row = (await session.execute(select(*_COLUMNS.values()).where(User.id == user_id))).one_or_none()
    result = {code: int(value or 0) for code, value in zip(_COLUMNS, row)} if row else {c: 0 for c in _COLUMNS}
    result[RES_TICKETS] = (await ticket_service.get_status(session, user_id)).count
    return {code: result[code] for code in RESOURCES}


async def spend(session: AsyncSession, user_id: int, code: str, amount: int) -> bool:
    """Списать, если хватает (одним условным UPDATE). False — не хватает. НЕ коммитит."""
    _check(code)
    if amount <= 0:
        return amount == 0
    if code == RES_TICKETS:
        return await ticket_service.spend(session, user_id, amount) is not None
    column = _COLUMNS[code]
    result = await session.execute(
        update(User).where(User.id == user_id, column >= amount).values({column: column + (-amount)})
    )
    return result.rowcount > 0


async def grant(session: AsyncSession, user_id: int, code: str, amount: int) -> None:
    """Начислить. НЕ коммитит."""
    _check(code)
    if amount <= 0:
        return
    if code == RES_TICKETS:
        await ticket_service.spend(session, user_id, 0)  # зафиксировать реген до начисления
        await ticket_service.refund(session, user_id, amount)
        return
    column = _COLUMNS[code]
    await session.execute(update(User).where(User.id == user_id).values({column: column + amount}))
