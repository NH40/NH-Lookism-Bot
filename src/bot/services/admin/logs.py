"""Админка — журналы (сервис): постраничные выборки платежей, покупок, активности."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.admin import LOG_BIG_MOVE_HOURS, LOG_BIG_MOVE_MIN
from bot.constant.ledger import ASSETS_MONEY


async def _page(session: AsyncSession, sql: str, count_sql: str, params: dict, offset: int, limit: int):
    rows = (await session.execute(text(sql + " LIMIT :lim OFFSET :off"), {**params, "lim": limit, "off": offset})).all()
    total = (await session.scalar(text(count_sql), params)) or 0
    return list(rows), int(total)


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


async def ledger_page(session: AsyncSession, user_id: int, assets: tuple[str, ...], *, offset: int = 0, limit: int = 15):
    """Журнал имущества игрока по видам. → ([(asset, item, delta, balance, note, reason, source, hits, created_at)], всего)."""
    where = "WHERE user_id = :u AND asset = ANY(CAST(:a AS varchar[]))"
    return await _page(
        session,
        f"SELECT asset, item, delta, balance, note, reason, source, hits, created_at FROM player_ledger {where} ORDER BY id DESC",
        f"SELECT count(*) FROM player_ledger {where}", {"u": user_id, "a": list(assets)}, offset, limit,
    )


async def big_moves_page(session: AsyncSession, *, offset: int = 0, limit: int = 15):
    """Крупные движения NHCoin и доната за сутки по всем игрокам, самые большие сверху."""
    where = ("WHERE l.created_at > now() - make_interval(hours => :h) AND abs(l.delta) >= :m AND l.asset = ANY(CAST(:a AS varchar[]))")
    params = {"h": LOG_BIG_MOVE_HOURS, "m": LOG_BIG_MOVE_MIN, "a": list(ASSETS_MONEY)}
    return await _page(
        session,
        "SELECT l.user_id, coalesce(u.display_name, u.username, l.user_id::text), l.asset, l.item, l.delta, l.balance, l.note, l.reason, l.source, l.hits, l.created_at "
        f"FROM player_ledger l LEFT JOIN users u ON u.id = l.user_id {where} ORDER BY abs(l.delta) DESC",
        f"SELECT count(*) FROM player_ledger l {where}", params, offset, limit,
    )


_BATTLE_SELECT = (
    "SELECT b.id, b.kind, b.attacker_id, b.defender_id, b.attacker_won, b.rounds, b.a_quantity, b.a_power, b.a_dead, b.a_fled, "
    "b.d_quantity, b.d_power, b.d_dead, b.d_fled, b.notes, b.details, b.source, b.created_at, "
    "coalesce(ua.display_name, ua.username, b.attacker_id::text) AS a_name, coalesce(ud.display_name, ud.username, b.defender_id::text) AS d_name "
    "FROM battle_log b LEFT JOIN users ua ON ua.id = b.attacker_id LEFT JOIN users ud ON ud.id = b.defender_id "
)


async def battles_page(session: AsyncSession, user_id: int, *, offset: int = 0, limit: int = 15):
    """Бои игрока: и нападения, и защита."""
    where = "WHERE b.attacker_id = :u OR b.defender_id = :u"
    return await _page(session, f"{_BATTLE_SELECT}{where} ORDER BY b.id DESC", f"SELECT count(*) FROM battle_log b {where}", {"u": user_id}, offset, limit)


async def upsets_page(session: AsyncSession, *, offset: int = 0, limit: int = 15):
    """Перекосы: игрок победил противника минимум вдвое сильнее — первое, что смотреть при жалобах на баланс."""
    where = ("WHERE b.defender_id IS NOT NULL AND ((b.attacker_won AND b.d_power >= b.a_power * 2) OR (NOT b.attacker_won AND b.a_power >= b.d_power * 2))")
    return await _page(session, f"{_BATTLE_SELECT}{where} ORDER BY b.id DESC", f"SELECT count(*) FROM battle_log b {where}", {}, offset, limit)


async def battle_row(session: AsyncSession, battle_id: int):
    return (await session.execute(text(f"{_BATTLE_SELECT}WHERE b.id = :b"), {"b": battle_id})).one_or_none()


async def errors_page(session: AsyncSession, kind: str, *, offset: int = 0, limit: int = 15):
    """Ошибки или медленные операции, свежие сверху."""
    return await _page(
        session,
        "SELECT id, process, title, detail, user_id, source, hits, max_ms, first_seen, last_seen FROM error_log WHERE kind = :k ORDER BY last_seen DESC",
        "SELECT count(*) FROM error_log WHERE kind = :k", {"k": kind}, offset, limit,
    )


async def error_row(session: AsyncSession, error_id: int):
    return (await session.execute(
        text("SELECT id, process, title, detail, user_id, source, hits, max_ms, first_seen, last_seen FROM error_log WHERE id = :i"), {"i": error_id}
    )).one_or_none()


async def activity_page(session: AsyncSession, user_id: int, *, offset: int = 0, limit: int = 15):
    """→ ([(kind, text, created_at)], всего)."""
    return await _page(
        session,
        "SELECT kind, text, created_at FROM activity_log WHERE user_id = :u ORDER BY id DESC",
        "SELECT count(*) FROM activity_log WHERE user_id = :u", {"u": user_id}, offset, limit,
    )
