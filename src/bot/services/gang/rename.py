"""Смена названия банды (пользователь 2026-11-12): `GANG_RENAME_PRICE` NHCoin, не чаще раза в
`GANG_RENAME_COOLDOWN_DAYS` дней. КД — `SET NX EX` (он же защита от двойного отправления),
списание — условный UPDATE (правило 1); не прошло — КД снимается."""
from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import gang_rename_cooldown
from bot.config.game import GANG_RENAME_COOLDOWN_DAYS, GANG_RENAME_PRICE
from bot.constant.ledger import REASON_GANG_RENAME
from bot.db.repositories import business as business_repo
from bot.services.gang.gang import validate_gang_name
from bot.utils.log_context import coin_reason


class RenameCooldownError(Exception):
    def __init__(self, seconds: int) -> None:
        super().__init__(seconds)
        self.seconds = seconds


class RenameNotEnoughError(Exception):
    pass


async def rename_cooldown(redis: Redis, user_id: int) -> int:
    return max(0, await redis.ttl(gang_rename_cooldown(user_id)))


async def rename_gang(session: AsyncSession, redis: Redis, user_id: int, raw_name: str) -> str:
    """Переименовать. Коммитит. → новое название. `InvalidGangNameError` — до КД и списания."""
    name = validate_gang_name(raw_name)
    key = gang_rename_cooldown(user_id)
    if not await redis.set(key, "1", nx=True, ex=GANG_RENAME_COOLDOWN_DAYS * 86400):
        raise RenameCooldownError(max(0, await redis.ttl(key)))
    try:
        with coin_reason(REASON_GANG_RENAME):
            if not await business_repo.spend_coins(session, user_id, GANG_RENAME_PRICE):
                raise RenameNotEnoughError
        await session.execute(text("UPDATE gangs SET name = :n WHERE user_id = :u"), {"n": name, "u": user_id})
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return name
