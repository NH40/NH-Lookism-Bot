"""Донат (сервис). Пользователь 2026-10-08:
- пополнение — как в UAP (ЮKassa через Telegram Payments, 1 ₽ = 1 донат-коин);
- чёрный рынок продаёт ускорение развития: второе тело (второй путь и вторая родословная),
  гениальности, пути и уникальные техники — открыть позицию и купить постоянные уровни;
- купленный уровень — «пол»: применяется при каждой выдаче позиции и заново после сброса
  прогресса (удаление банды, пробуждение) и патчей;
- донат LBP 1.3 (титулы + круги чёрного рынка + остаток NHDonate) переносится один раз.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.cache.keys import action_lock
from bot.config.development import MAX_LEVEL
from bot.config.donate import (
    GENIUS_LEVEL_PRICES,
    GENIUS_UNLOCK,
    LBP1_TITLE_PRICES,
    PATH_LEVEL_PRICES,
    PATH_UNLOCK,
    TECHNIQUE_LEVEL_PRICES,
    TECHNIQUE_UNLOCK,
    lbp1_circles_cost,
)
from bot.config.game import ACTION_LOCK_MS
from bot.constant.donate import KIND_GENIUS, KIND_PATH, KIND_TECHNIQUE, LOCK_ACTION_DONATE
from bot.constant.genius import GENIUSES
from bot.constant.unique_path import PATH_STAGE_OWNED, PATHS
from bot.constant.unique_technique import TECHNIQUES
from bot.db.repositories import donate as donate_repo
from bot.db.repositories import genius as genius_repo
from bot.db.repositories import unique_path as path_repo

logger = logging.getLogger(__name__)

CATALOG: dict[str, tuple[str, ...]] = {KIND_GENIUS: GENIUSES, KIND_PATH: PATHS, KIND_TECHNIQUE: TECHNIQUES}
_PRICES: dict[str, tuple[int, dict[int, int]]] = {
    KIND_GENIUS: (GENIUS_UNLOCK, GENIUS_LEVEL_PRICES),
    KIND_PATH: (PATH_UNLOCK, PATH_LEVEL_PRICES),
    KIND_TECHNIQUE: (TECHNIQUE_UNLOCK, TECHNIQUE_LEVEL_PRICES),
}


class DonateBusyError(Exception):
    pass


class NotEnoughDonateError(Exception):
    def __init__(self, price: int, balance: int) -> None:
        self.price = price
        self.balance = balance


class AlreadyBoughtError(Exception):
    pass


class NotUnlockedError(Exception):
    pass


class MaxLevelError(Exception):
    pass


class UnknownItemError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class MarketItem:
    kind: str
    code: str
    level: int  # купленный уровень, 0 — не открыто
    next_price: int | None  # цена открытия (level 0) или следующего уровня; None — максимум


def unlock_price(kind: str) -> int:
    return _PRICES[kind][0]


def item_view(kind: str, code: str, level: int) -> MarketItem:
    unlock, levels = _PRICES[kind]
    price = unlock if level == 0 else levels.get(level + 1)
    return MarketItem(kind, code, level, price)


async def balance(session: AsyncSession, user_id: int) -> int:
    return await donate_repo.balance(session, user_id)


async def credit_payment(
    session: AsyncSession, user_id: int, charge_id: str, provider_id: str, amount_rub: int
) -> int | None:
    """Зачислить успешный платёж (1 ₽ = 1 коин). → коины или None (повторная доставка). Коммитит."""
    if not await donate_repo.insert_payment(session, user_id, charge_id, provider_id, amount_rub, amount_rub):
        await session.rollback()
        return None
    await session.commit()
    return amount_rub


async def market(session: AsyncSession, user_id: int, kind: str) -> list[MarketItem]:
    bought = await donate_repo.unlocks(session, user_id, kind)
    return [item_view(kind, code, bought.get((kind, code), 0)) for code in CATALOG[kind]]


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_DONATE)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise DonateBusyError
    return key


async def _spend(session: AsyncSession, user_id: int, price: int) -> None:
    if not await donate_repo.spend(session, user_id, price):
        raise NotEnoughDonateError(price, await donate_repo.balance(session, user_id))


async def buy_second_body(session: AsyncSession, redis: Redis, user_id: int) -> None:
    """Второе тело — одно на аккаунт. Атомарно: флаг и списание одним UPDATE. Коммитит."""
    from bot.services.admin.live_config import get as live_get

    key = await _lock(redis, user_id)
    try:
        body = await donate_repo.body_state(session, user_id)
        if body and body[0]:
            raise AlreadyBoughtError
        if not await donate_repo.buy_second_body(session, user_id, live_get("second_body_price")):
            raise NotEnoughDonateError(live_get("second_body_price"), await donate_repo.balance(session, user_id))
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def _apply(session: AsyncSession, user_id: int, kind: str, code: str, level: int) -> None:
    """Применить покупку к игре: позиция у игрока, уровень не ниже купленного. НЕ коммитит.
    Путь выдаётся сразу, только если цепочка пути в этой жизни уже пройдена — иначе он станет
    вариантом выбора при пробуждении пути (пользователь)."""
    if kind == KIND_GENIUS:
        await genius_repo.add(session, user_id, code)
        await genius_repo.set_active_if_missing(session, user_id, code)
    elif kind == KIND_TECHNIQUE:
        from bot.services.unique_technique import grant as grant_technique  # домен техник тянет журнал/квесты

        await grant_technique(session, user_id, code)
    elif kind == KIND_PATH:
        state = await path_repo.get_state(session, user_id)
        if state and state[0] == PATH_STAGE_OWNED:
            await path_repo.add(session, user_id, code)
    await donate_repo.raise_owned_level(session, user_id, kind, code, level)


async def buy_unlock(session: AsyncSession, redis: Redis, user_id: int, kind: str, code: str) -> MarketItem:
    """Открыть позицию (гений/путь/технику). Коммитит."""
    if kind not in CATALOG or code not in CATALOG[kind]:
        raise UnknownItemError
    key = await _lock(redis, user_id)
    try:
        if not await donate_repo.add_unlock(session, user_id, kind, code):
            raise AlreadyBoughtError
        await _spend(session, user_id, unlock_price(kind))
        await _apply(session, user_id, kind, code, 1)
        await session.commit()
        return item_view(kind, code, 1)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def buy_level(session: AsyncSession, redis: Redis, user_id: int, kind: str, code: str) -> MarketItem:
    """Следующий постоянный уровень открытой позиции. Коммитит."""
    if kind not in CATALOG or code not in CATALOG[kind]:
        raise UnknownItemError
    key = await _lock(redis, user_id)
    try:
        current = await donate_repo.floor(session, user_id, kind, code)
        if not current:
            raise NotUnlockedError
        if current >= MAX_LEVEL:
            raise MaxLevelError
        price = _PRICES[kind][1][current + 1]
        if not await donate_repo.bump_unlock(session, user_id, kind, code, current):
            raise AlreadyBoughtError  # параллельная покупка того же уровня
        await _spend(session, user_id, price)
        await _apply(session, user_id, kind, code, current + 1)
        await session.commit()
        return item_view(kind, code, current + 1)
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def apply_all(session: AsyncSession, user_id: int) -> None:
    """После сброса прогресса: вернуть купленные техники и гении с их уровнями, поднять уровни
    уже полученных путей. НЕ коммитит."""
    for (kind, code), level in (await donate_repo.unlocks(session, user_id)).items():
        if kind == KIND_PATH:
            await donate_repo.raise_owned_level(session, user_id, kind, code, level)
        else:
            await _apply(session, user_id, kind, code, level)


# --- перенос доната LBP 1.3 ---


def _async_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


async def import_lbp1(session_factory: async_sessionmaker[AsyncSession], lbp1_url: str) -> int:
    """Один раз (пока таблица `lbp1_donations` пуста) посчитать донат каждого игрока 1.3 и
    зачислить тем, кто уже есть в 2.0; остальным — при первом /start (`claim_lbp1`).
    Сумма = титулы + круги + остаток NHDonate (покупки шли с баланса — платежи не прибавляем).
    → сколько игроков с донатом найдено."""
    async with session_factory() as session:
        if await donate_repo.lbp1_imported(session):
            await donate_repo.lbp1_credit(session)
            await session.commit()
            return 0
    engine = create_async_engine(_async_url(lbp1_url), pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as old:
            users = {uid: (tg, bal or 0) for uid, tg, bal in (await old.execute(text("SELECT id, tg_id, nh_donate FROM users"))).all()}
            titles: dict[int, int] = {}
            for uid, title_id in (await old.execute(text("SELECT user_id, title_id FROM user_donat_titles"))).all():
                titles[uid] = titles.get(uid, 0) + LBP1_TITLE_PRICES.get(title_id, 0)
            circles: dict[int, int] = {}
            for uid, donat_id, count in (await old.execute(text("SELECT user_id, donat_id, circles FROM user_circular_donats"))).all():
                circles[uid] = circles.get(uid, 0) + lbp1_circles_cost(donat_id, count or 0)
    finally:
        await engine.dispose()
    rows = []
    for uid, (tg_id, nh_donate) in users.items():
        t, c = titles.get(uid, 0), circles.get(uid, 0)
        total = t + c + max(nh_donate, 0)
        if total > 0:
            rows.append({"tg_id": tg_id, "titles": t, "circles": c, "balance": max(nh_donate, 0), "total": total})
    async with session_factory() as session:
        await donate_repo.lbp1_insert(session, rows)
        credited = await donate_repo.lbp1_credit(session)
        await session.commit()
    logger.info("LBP 1.3 donate import: %s donors, %s credited now", len(rows), credited)
    return len(rows)


async def claim_lbp1(session: AsyncSession, user_id: int) -> int:
    """Донат 1.3 игроку, который впервые пришёл в 2.0 после переноса. Коммитит, если начислено.
    → сколько коинов пришло."""
    rows = (
        await session.execute(
            text("SELECT total FROM lbp1_donations WHERE tg_id = :u AND credited_at IS NULL"), {"u": user_id}
        )
    ).scalar_one_or_none()
    if not rows or not await donate_repo.lbp1_credit(session, user_id):
        return 0
    await session.commit()
    return rows
