"""Патч (сброс прогресса всех игроков с сохранением доната) и вайп БД."""
from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.constant.admin.live_config import CONFIRM_TTL_SECONDS, PATCH_BATCH_SIZE, WIPE_KEEP_TABLES
from bot.db.base import Base
from bot.db.repositories.gang import reset_player
from bot.db.repositories.top import reset_powers
from bot.services.bloodline import apply_effects as apply_bloodline_effects
from bot.services.donate import apply_all as apply_donate

_running = False


def confirm_key(kind: str, admin_id: int) -> str:
    return f"flag:admin_{kind}_confirm:{admin_id}"


async def arm(redis: Redis, kind: str, admin_id: int) -> None:
    await redis.set(confirm_key(kind, admin_id), "1", ex=CONFIRM_TTL_SECONDS)


async def take(redis: Redis, kind: str, admin_id: int) -> bool:
    """Второе нажатие: забрать флаг атомарно. Нет флага — подтверждение истекло."""
    return bool(await redis.getdel(confirm_key(kind, admin_id)))


def is_running() -> bool:
    return _running


async def run_patch(session_factory: async_sessionmaker[AsyncSession], progress=None) -> int:
    """Сброс всех игроков пачками (у каждой пачки своя транзакция). `progress(done)` — колбэк."""
    from bot.services.admin.live_config import get as live_get

    global _running
    _running = True
    done, last = 0, 0
    try:
        coins, tickets = live_get("starting_nh_coins"), live_get("starting_tickets")
        while True:
            async with session_factory() as session:
                ids = (
                    await session.execute(
                        text("SELECT id FROM users WHERE id > :last ORDER BY id LIMIT :n"),
                        {"last": last, "n": PATCH_BATCH_SIZE},
                    )
                ).scalars().all()
                if not ids:
                    break
                for uid in ids:
                    await reset_player(session, uid, nh_coins=coins, tickets=tickets)
                    await apply_bloodline_effects(session, uid)
                    await apply_donate(session, uid)
                await session.commit()
            last, done = ids[-1], done + len(ids)
            if progress:
                await progress(done)
        async with session_factory() as session:
            await reset_powers(session)  # снимок мощи для топа — армии обнулены
            await session.commit()
    finally:
        _running = False
    return done


async def wipe_database(session: AsyncSession) -> list[str]:
    """TRUNCATE всех таблиц метаданных (кроме `WIPE_KEEP_TABLES`); alembic_version не в метаданных."""
    names = [t.name for t in Base.metadata.sorted_tables if t.name not in WIPE_KEEP_TABLES]
    await session.execute(text("TRUNCATE TABLE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
    await session.commit()
    return names
