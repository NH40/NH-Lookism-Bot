"""Battle Pass (репозиторий). Функции записи НЕ коммитят — коммитит сервис или вызывающая
транзакция (опыт пасса начисляется внутри действия игрока)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.battle_pass import BattlePass, BattlePassClaim, BpSeason


async def current_season(session: AsyncSession, now: datetime) -> BpSeason | None:
    return (
        await session.execute(
            select(BpSeason).where(BpSeason.starts_at <= now, BpSeason.ends_at > now).order_by(BpSeason.number.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def last_season(session: AsyncSession) -> BpSeason | None:
    return (await session.execute(select(BpSeason).order_by(BpSeason.number.desc()).limit(1))).scalar_one_or_none()


async def create_season(session: AsyncSession, number: int, starts_at: datetime, ends_at: datetime) -> None:
    """ON CONFLICT по номеру — два одновременных создания не дадут два сезона."""
    await session.execute(
        text(
            "INSERT INTO bp_seasons (number, starts_at, ends_at) VALUES (:n, :s, :e) ON CONFLICT (number) DO NOTHING"
        ),
        {"n": number, "s": starts_at, "e": ends_at},
    )


async def end_season(session: AsyncSession, season_id: int, now: datetime) -> None:
    await session.execute(update(BpSeason).where(BpSeason.id == season_id).values(ends_at=now))


async def get(session: AsyncSession, user_id: int, season_id: int) -> BattlePass | None:
    return await session.get(BattlePass, (user_id, season_id))


async def lock(session: AsyncSession, user_id: int, season_id: int) -> BattlePass:
    """Пасс игрока под `FOR UPDATE` (создаётся при первом обращении)."""
    await session.execute(
        text("INSERT INTO battle_passes (user_id, season_id) VALUES (:u, :s) ON CONFLICT DO NOTHING"),
        {"u": user_id, "s": season_id},
    )
    return (
        await session.execute(
            select(BattlePass)
            .where(BattlePass.user_id == user_id, BattlePass.season_id == season_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def claimed_levels(session: AsyncSession, user_id: int, season_id: int, track: str, above: int) -> list[int]:
    """Уровни, забранные вне очереди, выше high-water mark (по возрастанию)."""
    rows = await session.execute(
        select(BattlePassClaim.level)
        .where(
            BattlePassClaim.user_id == user_id,
            BattlePassClaim.season_id == season_id,
            BattlePassClaim.track == track,
            BattlePassClaim.level > above,
        )
        .order_by(BattlePassClaim.level)
    )
    return list(rows.scalars().all())


async def claimed_in_range(
    session: AsyncSession, user_id: int, season_id: int, low: int, high: int
) -> set[tuple[str, int]]:
    rows = await session.execute(
        select(BattlePassClaim.track, BattlePassClaim.level).where(
            BattlePassClaim.user_id == user_id,
            BattlePassClaim.season_id == season_id,
            BattlePassClaim.level.between(low, high),
        )
    )
    return {(t, lvl) for t, lvl in rows.all()}


async def add_claim(session: AsyncSession, user_id: int, season_id: int, track: str, level: int) -> bool:
    result = await session.execute(
        text(
            "INSERT INTO battle_pass_claims (user_id, season_id, track, level) VALUES (:u, :s, :t, :l) "
            "ON CONFLICT DO NOTHING"
        ),
        {"u": user_id, "s": season_id, "t": track, "l": level},
    )
    return result.rowcount > 0


async def drop_claims(session: AsyncSession, user_id: int, season_id: int, track: str, up_to: int) -> None:
    await session.execute(
        delete(BattlePassClaim).where(
            BattlePassClaim.user_id == user_id,
            BattlePassClaim.season_id == season_id,
            BattlePassClaim.track == track,
            BattlePassClaim.level <= up_to,
        )
    )


async def add_skip_scrolls(session: AsyncSession, user_id: int, n: int) -> None:
    await session.execute(text("UPDATE users SET skip_scrolls = skip_scrolls + :n WHERE id = :u"), {"u": user_id, "n": n})


async def spend_skip_scroll(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        text("UPDATE users SET skip_scrolls = skip_scrolls - 1 WHERE id = :u AND skip_scrolls > 0"), {"u": user_id}
    )
    return result.rowcount > 0


async def skip_scrolls(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(text("SELECT skip_scrolls FROM users WHERE id = :u"), {"u": user_id})).scalar_one()


async def premium_count(session: AsyncSession, season_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(BattlePass).where(BattlePass.season_id == season_id, BattlePass.is_premium)
        )
    ).scalar_one()


