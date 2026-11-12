"""«Пятницы» — скидки и разовые покупки (пользователь 2026-11-12, идеи игроков).

Админ запускает одну пятницу (новая — только когда текущей нет), через `SALE_HOURS` она
заканчивается сама (ленивая проверка `now() < ends_at`, без фона), выключить можно раньше.

- скидка на категорию — `discounted(session, user_id, category, price)` вызывают все донат-покупки
  (гении/пути/техники, второе тело, премиум и уровни пасса, уровень клана);
- пополнение — `topup_coins(session, amount_rub)`: «силы» (дешевле на 10% = коинов больше) и
  «золотая» (+5% коинов);
- «избранных» — игрок сам выбирает до `SALE_CHOSEN_MAX` категорий;
- разовые покупки (одна на игрока за пятницу): смена родословной (выдаёт право бесплатной
  смены), этап пробуждения (+1 без сброса, пользователь), уровень родословной.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS
from bot.config.sale import (
    SALE_AWAKEN_PRICE,
    SALE_BLOOD_LEVEL_PRICE,
    SALE_CHOSEN_MAX,
    SALE_CHOSEN_PERCENT,
    SALE_DISCOUNTS,
    SALE_GOLDEN_PERCENT,
    SALE_HOURS,
    SALE_POWER_PERCENT,
    SALE_REBIRTH_PRICE,
)
from bot.constant.sale import (
    CATEGORIES,
    LOCK_ACTION_SALE,
    SALE_AWAKEN,
    SALE_BLOOD_LEVEL,
    SALE_CHOSEN,
    SALE_GOLDEN,
    SALE_KINDS,
    SALE_POWER,
    SALE_REBIRTH,
    SPECIAL_SALES,
)
from bot.db.models.sale import SaleChoice, SaleEvent


class SaleActiveError(Exception):
    """Уже идёт другая пятница."""


class NoSaleError(Exception):
    pass


class SaleBusyError(Exception):
    pass


class AlreadyBoughtError(Exception):
    pass


class NotEnoughDonateError(Exception):
    def __init__(self, price: int, balance: int) -> None:
        super().__init__(price, balance)
        self.price = price
        self.balance = balance


class CannotBuyError(Exception):
    """Покупка недоступна игроку (нет родословной, максимум пробуждения/уровня)."""


class TooManyChoicesError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def active(session: AsyncSession) -> SaleEvent | None:
    return await session.scalar(
        select(SaleEvent).where(SaleEvent.stopped_at.is_(None), SaleEvent.ends_at > func.now()).order_by(SaleEvent.id.desc()).limit(1)
    )


# --- админ ---


async def start(session: AsyncSession, kind: str, admin_id: int) -> SaleEvent:
    """Запустить пятницу на `SALE_HOURS`. Коммитит. Двойной клик — вторая увидит активную."""
    if kind not in SALE_KINDS:
        raise NoSaleError
    await session.execute(text("SELECT pg_advisory_xact_lock(4242001)"))  # одна пятница: запуск по очереди
    if await active(session) is not None:
        raise SaleActiveError
    row = SaleEvent(kind=kind, started_by=admin_id, ends_at=_now() + timedelta(hours=SALE_HOURS))
    session.add(row)
    await session.commit()
    return row


async def stop(session: AsyncSession) -> SaleEvent | None:
    """Выключить текущую раньше срока. Коммитит. → остановленная или None."""
    row = await active(session)
    if row is None:
        return None
    row.stopped_at = _now()
    await session.commit()
    return row


# --- скидки ---


async def _choices(session: AsyncSession, event_id: int, user_id: int) -> list[str]:
    return list(await session.scalar(
        select(SaleChoice.categories).where(SaleChoice.event_id == event_id, SaleChoice.user_id == user_id)
    ) or [])


async def discount_percent(session: AsyncSession, user_id: int, category: str, sale: SaleEvent | None = None) -> int:
    sale = sale or await active(session)
    if sale is None:
        return 0
    if sale.kind == SALE_CHOSEN:
        return SALE_CHOSEN_PERCENT if category in await _choices(session, sale.id, user_id) else 0
    return SALE_DISCOUNTS.get(sale.kind, {}).get(category, 0)


def apply_percent(price: int, percent: int) -> int:
    """Цена со скидкой, округление вверх (не меньше 1)."""
    if not percent:
        return price
    return max(1, math.ceil(price * (100 - percent) / 100))


async def discounted(session: AsyncSession, user_id: int, category: str, price: int) -> int:
    """Цена донат-покупки с учётом текущей пятницы."""
    return apply_percent(price, await discount_percent(session, user_id, category))


async def topup_coins(session: AsyncSession, amount_rub: int) -> int:
    """Сколько коинов за пополнение на `amount_rub` ₽ (обычно 1:1)."""
    sale = await active(session)
    if sale is None:
        return amount_rub
    if sale.kind == SALE_POWER:  # «скидка на пополнение»: заплатил 90 — получил 100
        return math.floor(amount_rub * 100 / (100 - SALE_POWER_PERCENT))
    if sale.kind == SALE_GOLDEN:
        return amount_rub + amount_rub * SALE_GOLDEN_PERCENT // 100
    return amount_rub


# --- «избранных» ---


async def toggle_choice(session: AsyncSession, user_id: int, category: str) -> list[str]:
    """Выбрать или снять категорию (до `SALE_CHOSEN_MAX`). Коммитит. → выбранные."""
    sale = await active(session)
    if sale is None or sale.kind != SALE_CHOSEN:
        raise NoSaleError
    if category not in CATEGORIES:
        raise NoSaleError
    current = await _choices(session, sale.id, user_id)
    if category in current:
        current.remove(category)
    elif len(current) >= SALE_CHOSEN_MAX:
        raise TooManyChoicesError
    else:
        current.append(category)
    await session.execute(text(
        "INSERT INTO sale_choices (event_id, user_id, categories) VALUES (:e, :u, :c) "
        "ON CONFLICT (event_id, user_id) DO UPDATE SET categories = EXCLUDED.categories"
    ), {"e": sale.id, "u": user_id, "c": current})
    await session.commit()
    return current


# --- разовые покупки ---

SPECIAL_PRICES = {SALE_REBIRTH: SALE_REBIRTH_PRICE, SALE_AWAKEN: SALE_AWAKEN_PRICE, SALE_BLOOD_LEVEL: SALE_BLOOD_LEVEL_PRICE}


@dataclass(frozen=True, slots=True)
class SaleView:
    sale: SaleEvent | None
    left_seconds: int
    choices: list[str]
    bought: bool  # разовая покупка этой пятницы уже сделана


async def view(session: AsyncSession, user_id: int) -> SaleView:
    sale = await active(session)
    if sale is None:
        return SaleView(None, 0, [], False)
    bought = bool(await session.scalar(text(
        "SELECT EXISTS(SELECT 1 FROM sale_purchases WHERE event_id = :e AND user_id = :u)"
    ), {"e": sale.id, "u": user_id}))
    return SaleView(
        sale, max(0, int((sale.ends_at - _now()).total_seconds())),
        await _choices(session, sale.id, user_id) if sale.kind == SALE_CHOSEN else [], bought,
    )


async def buy_special(session: AsyncSession, redis: Redis, user_id: int) -> str:
    """Разовая покупка текущей пятницы. Строка игрока под FOR UPDATE, PK покупки — от двойного
    клика, списание — условный UPDATE (правило 1). Коммитит. → вид покупки."""
    from bot.config.awakening import AWAKENING_MAX
    from bot.config.development import MAX_LEVEL
    from bot.db.repositories import donate as donate_repo
    from bot.db.models.user import User
    from bot.services.bloodline import apply_effects as apply_bloodline_effects

    key = action_lock(user_id, LOCK_ACTION_SALE)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise SaleBusyError
    try:
        sale = await active(session)
        if sale is None or sale.kind not in SPECIAL_SALES:
            raise NoSaleError
        user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            raise CannotBuyError
        if sale.kind == SALE_REBIRTH and (user.bloodline is None or user.free_bloodline_change):
            raise CannotBuyError
        if sale.kind == SALE_AWAKEN and user.awakening_level >= AWAKENING_MAX:
            raise CannotBuyError
        if sale.kind == SALE_BLOOD_LEVEL and (user.bloodline is None or user.bloodline_level >= MAX_LEVEL):
            raise CannotBuyError
        inserted = await session.scalar(text(
            "INSERT INTO sale_purchases (event_id, user_id) VALUES (:e, :u) ON CONFLICT DO NOTHING RETURNING event_id"
        ), {"e": sale.id, "u": user_id})
        if inserted is None:
            raise AlreadyBoughtError
        price = SPECIAL_PRICES[sale.kind]
        if not await donate_repo.spend(session, user_id, price):
            raise NotEnoughDonateError(price, await donate_repo.balance(session, user_id))
        if sale.kind == SALE_REBIRTH:
            await session.execute(update(User).where(User.id == user_id).values(free_bloodline_change=True))
        elif sale.kind == SALE_AWAKEN:
            await session.execute(update(User).where(User.id == user_id).values(awakening_level=User.awakening_level + 1))
        else:
            await session.execute(update(User).where(User.id == user_id).values(bloodline_level=User.bloodline_level + 1))
            await apply_bloodline_effects(session, user_id)
        await session.commit()
        return sale.kind
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)
