"""Ячейки хранения (сервис). Дизайн — `config/storage`.

Ячейка держит один вид вещи — ресурс или отряд статистов — и защищает его: лежащее в ячейке
не на балансе и не в лагерях, поэтому его не крадёт саботаж, не забирает война и не убивает
бой. Сгорает содержимое только при пробуждении и удалении банды (сами ячейки остаются).
Плата за хранение копится, пока ячейка не пуста, и платится при выемке (без неё вещь не
достать). Все операции — лок на клик (правило 2) + строка ячейки `FOR UPDATE` + атомарные
списания (правило 1) + один commit.
"""
from __future__ import annotations

from bot.config.absolute import HASBULLA_SHOP_DISCOUNT
from bot.constant.absolute import ABS_HASBULLA
from bot.services.build import get_build
from bot.constant.dev_quest import TASK_STORAGE

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS
from bot.config.storage import STORAGE_DEBT_CAP_HOURS, STORAGE_FEE_PER_HOUR, STORAGE_OPEN_COSTS, STORAGE_SLOTS
from bot.constant.resource import RESOURCES
from bot.constant.storage import LOCK_ACTION_STORAGE, STORAGE_ITEM_EMPTY, STORAGE_ITEM_RESOURCE, STORAGE_ITEM_STATIST
from bot.db.repositories import business as business_repo
from bot.db.repositories import storage as storage_repo
from bot.services.resource import StatistKey, give_statists, grant, spend, take_statists


class StorageBusyError(Exception):
    pass


class CellLockedError(Exception):
    """Ячейка не куплена (или открывать нужно по порядку)."""


class CellOccupiedError(Exception):
    """В ячейке уже лежит другая вещь."""


class CellEmptyError(Exception):
    pass


class InvalidAmountError(Exception):
    pass


class NotEnoughError(Exception):
    """Не хватает того, что кладут (ресурса или бойцов отряда)."""


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int) -> None:
        super().__init__(cost)
        self.cost = cost


@dataclass(frozen=True, slots=True)
class CellView:
    slot: int
    opened: bool
    kind: str
    code: str
    amount: int
    debt: int
    open_cost: int  # цена открытия (для закрытой)

    @property
    def empty(self) -> bool:
        return self.kind == STORAGE_ITEM_EMPTY or self.amount <= 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def debt_for(fee_from: datetime, now: datetime | None = None, discount: float = 0.0) -> int:
    """`discount` — «Логистика» Бизнесмена (плата за ячейки меньше)."""
    hours = max(0.0, ((now or _now()) - fee_from).total_seconds() / 3600)
    return int(min(hours, STORAGE_DEBT_CAP_HOURS) * STORAGE_FEE_PER_HOUR * (1 - min(0.8, discount)))


async def cells(session: AsyncSession, user_id: int) -> list[CellView]:
    rows = {c.slot: c for c in await storage_repo.list_cells(session, user_id)}
    now = _now()
    result = []
    for slot in range(1, STORAGE_SLOTS + 1):
        row = rows.get(slot)
        if row is None:
            result.append(CellView(slot, False, STORAGE_ITEM_EMPTY, "", 0, 0, STORAGE_OPEN_COSTS[slot - 1]))
            continue
        filled = row.item_kind != STORAGE_ITEM_EMPTY and row.amount > 0
        result.append(CellView(slot, True, row.item_kind, row.item_code, row.amount, debt_for(row.fee_from, now) if filled else 0, 0))
    return result


async def _locked(redis: Redis, user_id: int):
    key = action_lock(user_id, LOCK_ACTION_STORAGE)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise StorageBusyError
    return key


async def open_cell(session: AsyncSession, redis: Redis, user_id: int, slot: int) -> int:
    """Купить ячейку (по порядку). → цена. Коммитит."""
    opened = {c.slot for c in await storage_repo.list_cells(session, user_id)}
    if not 1 <= slot <= STORAGE_SLOTS or slot in opened or slot != len(opened) + 1:
        raise CellLockedError
    key = await _locked(redis, user_id)
    try:
        cost = STORAGE_OPEN_COSTS[slot - 1]
        if ABS_HASBULLA in (await get_build(session, user_id)).absolutes:  # абсолют: скидка в магазине
            cost = int(cost * (1 - HASBULLA_SHOP_DISCOUNT))
        if not await business_repo.spend_coins(session, user_id, cost):
            raise NotEnoughCoinsError(cost)
        if not await storage_repo.create(session, user_id, slot):
            await session.rollback()
            raise CellLockedError
        await session.commit()
        return cost
    finally:
        await redis.delete(key)


async def _cell_for_put(session: AsyncSession, user_id: int, slot: int, kind: str, code: str):
    cell = await storage_repo.get_for_update(session, user_id, slot)
    if cell is None:
        raise CellLockedError
    filled = cell.item_kind != STORAGE_ITEM_EMPTY and cell.amount > 0
    if filled and (cell.item_kind, cell.item_code) != (kind, code):
        raise CellOccupiedError
    return cell, filled


async def store_resource(session: AsyncSession, redis: Redis, user_id: int, slot: int, code: str, amount: int) -> int:
    """Положить ресурс (или доложить тот же). → сколько теперь в ячейке. Коммитит."""
    if code not in RESOURCES:
        raise InvalidAmountError
    if amount <= 0:
        raise InvalidAmountError
    key = await _locked(redis, user_id)
    try:
        cell, filled = await _cell_for_put(session, user_id, slot, STORAGE_ITEM_RESOURCE, code)
        if not await spend(session, user_id, code, amount):
            await session.rollback()
            raise NotEnoughError
        total = (cell.amount if filled else 0) + amount
        await storage_repo.put(session, user_id, slot, STORAGE_ITEM_RESOURCE, code, total, cell.fee_from if filled else _now())
        await quest_event(session, user_id, TASK_STORAGE)
        await session.commit()
        return total
    finally:
        await redis.delete(key)


async def store_statists(session: AsyncSession, redis: Redis, user_id: int, slot: int, statist: StatistKey, amount: int) -> int:
    """Положить бойцов отряда (из защиты, потом из атаки). → сколько теперь в ячейке. Коммитит."""
    if amount <= 0:
        raise InvalidAmountError
    key = await _locked(redis, user_id)
    try:
        code = statist.encode()
        cell, filled = await _cell_for_put(session, user_id, slot, STORAGE_ITEM_STATIST, code)
        if not await take_statists(session, user_id, statist, amount):
            await session.rollback()
            raise NotEnoughError
        total = (cell.amount if filled else 0) + amount
        await storage_repo.put(session, user_id, slot, STORAGE_ITEM_STATIST, code, total, cell.fee_from if filled else _now())
        await quest_event(session, user_id, TASK_STORAGE)
        await session.commit()
        return total
    finally:
        await redis.delete(key)


async def retrieve(session: AsyncSession, redis: Redis, user_id: int, slot: int, amount: int | None = None) -> tuple[int, int]:
    """Достать всё (`amount=None`) или часть. Сначала платится долг за хранение — без него вещь
    не выдаётся. Остаток продолжает копить плату с этого момента. → (выдано, заплачено).
    Коммитит."""
    key = await _locked(redis, user_id)
    try:
        cell = await storage_repo.get_for_update(session, user_id, slot)
        if cell is None:
            raise CellLockedError
        if cell.item_kind == STORAGE_ITEM_EMPTY or cell.amount <= 0:
            raise CellEmptyError
        take = cell.amount if amount is None else amount
        if not 0 < take <= cell.amount:
            raise InvalidAmountError
        now = _now()
        positions = (await get_build(session, user_id)).positions
        debt = debt_for(cell.fee_from, now, positions.get("storage_fee") if positions is not None else 0.0)
        if debt and not await business_repo.spend_coins(session, user_id, debt):
            raise NotEnoughCoinsError(debt)
        if cell.item_kind == STORAGE_ITEM_RESOURCE:
            await grant(session, user_id, cell.item_code, take)
        else:
            await give_statists(session, user_id, StatistKey.decode(cell.item_code), take)
        left = cell.amount - take
        if left:
            await storage_repo.put(session, user_id, slot, cell.item_kind, cell.item_code, left, now)
        else:
            await storage_repo.put(session, user_id, slot, STORAGE_ITEM_EMPTY, "", 0, now)
        await session.commit()
        return take, debt
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)
