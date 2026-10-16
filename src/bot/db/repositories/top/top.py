"""Топ игроков/кланов и список игроков (репозиторий).

Сортировка — по снимку мощи `users.army_power_cache` (индекс), не живым расчётом: живая мощь
армии — несколько запросов на игрока, по всем игрокам её не посчитать (правило 3).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.clan import Clan, ClanMember
from bot.db.models.user import User


@dataclass(frozen=True, slots=True)
class PlayerRow:
    user_id: int
    name: str
    phase: str
    power: int
    clan: str | None


def _listed():
    """В топе и списке — зарегистрированные (есть город) и не забаненные."""
    return and_(
        User.city_id.is_not(None),
        User.is_banned.is_(False),
        or_(User.banned_until.is_(None), User.banned_until <= func.now()),
    )


async def active_user_ids(session: AsyncSession, since: datetime) -> list[int]:
    rows = await session.scalars(select(User.id).where(User.city_id.is_not(None), User.last_active_at >= since).order_by(User.id))
    return list(rows.all())


async def onboarded_user_ids(session: AsyncSession) -> list[int]:
    rows = await session.scalars(select(User.id).where(User.city_id.is_not(None)).order_by(User.id))
    return list(rows.all())


async def set_powers(session: AsyncSession, values: list[tuple[int, int]]) -> None:
    """Пачка снимков мощи одним executemany. НЕ коммитит."""
    if values:
        await session.execute(
            text("UPDATE users SET army_power_cache = :p WHERE id = :u"), [{"u": u, "p": p} for u, p in values]
        )


async def reset_powers(session: AsyncSession) -> None:
    """После патча армии обнулены — снимки тоже (иначе неактивные висели бы в топе со старой мощью)."""
    await session.execute(update(User).values(army_power_cache=0))


async def players_page(session: AsyncSession, limit: int, offset: int) -> list[PlayerRow]:
    rows = await session.execute(
        select(
            User.id, func.coalesce(User.display_name, User.username, "Игрок"), User.phase, User.army_power_cache, Clan.name
        )
        .outerjoin(ClanMember, ClanMember.user_id == User.id)
        .outerjoin(Clan, Clan.id == ClanMember.clan_id)
        .where(_listed())
        .order_by(User.army_power_cache.desc(), User.id)
        .limit(limit)
        .offset(offset)
    )
    return [PlayerRow(*row) for row in rows.all()]


async def count_players(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(User.id)).where(_listed())) or 0)


async def rank_of(session: AsyncSession, user_id: int) -> tuple[int, int] | None:
    """→ (место, мощь-снимок) игрока в топе; None — его нет в списке (бан/не зарегистрирован)."""
    me = await session.execute(select(User.army_power_cache).where(User.id == user_id, _listed()))
    power = me.scalar_one_or_none()
    if power is None:
        return None
    ahead = await session.scalar(
        select(func.count(User.id)).where(
            _listed(), or_(User.army_power_cache > power, and_(User.army_power_cache == power, User.id < user_id))
        )
    )
    return int(ahead or 0) + 1, int(power)


async def claim_payout(session: AsyncSession, key: str) -> bool:
    """Застолбить выплату сезона (PK). False — уже выплачено. НЕ коммитит."""
    got = await session.scalar(
        text("INSERT INTO season_top_payouts (key) VALUES (:k) ON CONFLICT (key) DO NOTHING RETURNING key"), {"k": key}
    )
    return got is not None


async def unpaid_ended_seasons(session: AsyncSession, since: datetime) -> list[int]:
    """Номера сезонов Battle Pass, закончившихся после `since`, по которым топ ещё не выплачен."""
    rows = await session.scalars(
        text(
            "SELECT number FROM bp_seasons WHERE ends_at <= now() AND ends_at >= :since "
            "AND 'bp:' || number NOT IN (SELECT key FROM season_top_payouts) ORDER BY number"
        ),
        {"since": since},
    )
    return list(rows.all())


async def credit(session: AsyncSession, user_id: int, *, donate: int, coins: int, ticket_values: dict) -> None:
    """Начислить награду топа одним UPDATE. `ticket_values` — колонки тикетов с регеном
    (`services.admin.mass.ticket_grant_values`). НЕ коммитит."""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values({User.donate_coins: User.donate_coins + donate, User.nh_coins: User.nh_coins + coins, **ticket_values})
    )
