"""Настройки на лету: реестр ключей, кэш в памяти (загружается при старте), запись в `game_settings`.

`get(key)` — синхронный: переопределение (если не истекло) или значение по умолчанию из config.
Пишут и бот, и API Mini App (админка в Mini App, 2026-10-17) — у каждого процесса свой кэш,
поэтому оба перечитывают таблицу раз в `LIVE_CONFIG_REFRESH_SECONDS` (`refresh_loop`): правка из
другого процесса доходит с этой задержкой, свой процесс видит её сразу."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.constant.admin.live_config import (
    AUDIT_CONFIG_RESET,
    AUDIT_CONFIG_SET,
    KEY_BODY_PRICE,
    KEY_BP_PRICE,
    KEY_BP_XP_MULT,
    KEY_INCOME_MULT,
    KEY_START_COINS,
    KEY_START_TICKETS,
)
from bot.db.models.admin import GameSetting
from bot.services.admin import audit

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveKey:
    key: str
    title: str
    type: type  # int | float
    min: float
    max: float
    default: Callable[[], float]
    expiring: bool = False  # множители — с необязательным сроком


def _d_bp_price() -> int:
    from bot.config.battle_pass import BP_PREMIUM_PRICE

    return BP_PREMIUM_PRICE


def _d_body_price() -> int:
    from bot.config.donate import SECOND_BODY_PRICE

    return SECOND_BODY_PRICE


def _d_coins() -> int:
    from bot.config.game import NH_COINS_STARTING

    return NH_COINS_STARTING


def _d_tickets() -> int:
    from bot.config.game import TICKET_STARTING

    return TICKET_STARTING


LIVE_KEYS: dict[str, LiveKey] = {
    k.key: k
    for k in (
        LiveKey(KEY_BP_XP_MULT, "Множитель опыта пасса", float, 0.1, 10.0, lambda: 1.0, True),
        LiveKey(KEY_INCOME_MULT, "Множитель дохода бизнеса", float, 0.1, 10.0, lambda: 1.0, True),
        LiveKey(KEY_START_COINS, "Стартовые NHCoin новичка", int, 0, 10_000_000, _d_coins),
        LiveKey(KEY_START_TICKETS, "Стартовые тикеты новичка", int, 0, 10_000, _d_tickets),
        LiveKey(KEY_BP_PRICE, "Цена премиум-пасса (донат-коины)", int, 0, 1_000_000, _d_bp_price),
        LiveKey(KEY_BODY_PRICE, "Цена второго тела (донат-коины)", int, 0, 10_000_000, _d_body_price),
    )
}

_cache: dict[str, tuple[float, datetime | None]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: dict) -> tuple[float, datetime | None] | None:
    try:
        until = raw.get("until")
        return raw["value"], (datetime.fromisoformat(until) if until else None)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


async def refresh_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Фоновое перечитывание переопределений (бот и API — разные процессы, см. докстринг)."""
    import asyncio

    from bot.config.admin import LIVE_CONFIG_REFRESH_SECONDS

    while True:
        await asyncio.sleep(LIVE_CONFIG_REFRESH_SECONDS)
        try:
            await load(session_factory, quiet=True)
        except Exception:  # noqa: BLE001 — БД недоступна: попробуем в следующий раз
            log.exception("Live config refresh failed")


async def load(session_factory: async_sessionmaker[AsyncSession], *, quiet: bool = False) -> None:
    async with session_factory() as session:
        rows = (await session.execute(select(GameSetting).where(GameSetting.key.in_(list(LIVE_KEYS))))).scalars().all()
    _cache.clear()
    for row in rows:
        parsed = _parse(row.value)
        if parsed:
            _cache[row.key] = parsed
    if not quiet:
        log.info("Live config loaded: %d overrides", len(_cache))


def override(key: str) -> tuple[float, datetime | None] | None:
    """Действующее переопределение (не истёкшее) или None."""
    entry = _cache.get(key)
    if entry is None or (entry[1] is not None and entry[1] <= _now()):
        return None
    return entry


def get(key: str):
    entry = override(key)
    spec = LIVE_KEYS[key]
    return spec.type(entry[0]) if entry else spec.default()


def validate(key: str, raw: str) -> float | None:
    spec = LIVE_KEYS[key]
    try:
        value = spec.type(raw.strip().replace(",", ".") if spec.type is float else raw.strip())
    except ValueError:
        return None
    return value if spec.min <= value <= spec.max else None


async def set_value(session: AsyncSession, admin_id: int, key: str, value: float, hours: int = 0) -> None:
    """Записать переопределение (hours=0 — навсегда). Коммитит."""
    until = _now() + timedelta(hours=hours) if hours else None
    payload = {"value": value, "until": until.isoformat() if until else None}
    stmt = insert(GameSetting).values(key=key, value=payload, updated_by=admin_id)
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["key"], set_={"value": payload, "updated_by": admin_id})
    )
    await audit.log(session, admin_id, AUDIT_CONFIG_SET, None, {"key": key, "value": value, "hours": hours})
    await session.commit()
    _cache[key] = (value, until)


async def reset(session: AsyncSession, admin_id: int, key: str) -> None:
    await session.execute(delete(GameSetting).where(GameSetting.key == key))
    await audit.log(session, admin_id, AUDIT_CONFIG_RESET, None, {"key": key})
    await session.commit()
    _cache.pop(key, None)
