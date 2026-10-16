"""Админка — журналы (сервис): постраничные выборки платежей, покупок, активности."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _page(session: AsyncSession, sql: str, count_sql: str, params: dict, offset: int, limit: int):
    rows = (await session.execute(text(sql + " LIMIT :lim OFFSET :off"), {**params, "lim": limit, "off": offset})).all()
    total = (await session.scalar(text(count_sql), params)) or 0
    return [tuple(r) for r in rows], int(total)


async def payments_page(session: AsyncSession, *, user_id: int | None = None, offset: int = 0, limit: int = 15):
    """→ ([(user_id, username, rub, coins, created_at)], всего)."""
    where = "WHERE p.user_id = :u" if user_id is not None else ""
    return await _page(
        session,
        f"SELECT p.user_id, u.username, p.amount_rub, p.coins, p.created_at FROM payments p "
        f"LEFT JOIN users u ON u.id = p.user_id {where} ORDER BY p.id DESC",
        f"SELECT count(*) FROM payments p {where}",
        {"u": user_id} if user_id is not None else {}, offset, limit,
    )


async def clan_purchases_page(session: AsyncSession, *, offset: int = 0, limit: int = 15):
    """→ ([(clan_name, user_id, username, price, created_at)], всего)."""
    return await _page(
        session,
        "SELECT c.name, d.user_id, u.username, d.price, d.created_at FROM clan_donate_purchases d "
        "JOIN clans c ON c.id = d.clan_id LEFT JOIN users u ON u.id = d.user_id ORDER BY d.id DESC",
        "SELECT count(*) FROM clan_donate_purchases", {}, offset, limit,
    )


async def blackmarket_summary(session: AsyncSession) -> list[tuple[str, str, int, int]]:
    """Без временных меток в таблице — сводка: (kind, code, покупателей, макс. уровень)."""
    rows = await session.execute(text(
        "SELECT kind, code, count(*), max(level) FROM donate_unlocks GROUP BY kind, code ORDER BY count(*) DESC, kind, code LIMIT 40"
    ))
    return [tuple(r) for r in rows.all()]


async def activity_page(session: AsyncSession, user_id: int, *, offset: int = 0, limit: int = 15):
    """→ ([(kind, text, created_at)], всего)."""
    return await _page(
        session,
        "SELECT kind, text, created_at FROM activity_log WHERE user_id = :u ORDER BY id DESC",
        "SELECT count(*) FROM activity_log WHERE user_id = :u", {"u": user_id}, offset, limit,
    )
