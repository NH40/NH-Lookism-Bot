"""Админка: поиск игрока и данные карточки (сервис, только чтение)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.battle_pass import level_from_xp
from bot.db.models.user import User
from bot.db.repositories import battle_pass as bp_repo
from bot.db.repositories.user import find_by_username, get_by_id
from bot.services.resource import balances


@dataclass(frozen=True, slots=True)
class PlayerCard:
    user: User
    role: str | None
    banned: bool
    gang: str | None
    city: str | None
    districts: int
    clan: str | None
    resources: dict[str, int]
    paths: list[tuple[str, int]]
    techniques: list[tuple[str, int]]
    geniuses: list[tuple[str, int]]
    bp_level: int
    bp_premium: bool
    donated_rub: int
    donate_unlocks: int


async def find(session: AsyncSession, query: str) -> User | None:
    """Игрок по id или @нику (с @ или без)."""
    query = query.strip()
    if query.lstrip("-").isdigit():
        return await get_by_id(session, int(query))
    return await find_by_username(session, query.lstrip("@"))


def is_banned(user: User) -> bool:
    return bool(user.is_banned or (user.banned_until and user.banned_until > datetime.now(timezone.utc)))


async def _owned(session: AsyncSession, table: str, user_id: int) -> list[tuple[str, int]]:
    rows = await session.execute(text(f"SELECT code, level FROM {table} WHERE user_id = :u ORDER BY code"), {"u": user_id})
    return [(c, lvl) for c, lvl in rows.all()]


async def card(session: AsyncSession, user_id: int) -> PlayerCard | None:
    from bot.services.admin.roles import role_of  # roles → settings; без цикла на импорте

    user = await get_by_id(session, user_id)
    if user is None:
        return None
    info = (
        await session.execute(
            text(
                """
                SELECT g.name, c.name,
                       (SELECT count(*) FROM districts d WHERE d.owner_id = u.id),
                       (SELECT cl.name FROM clan_members m JOIN clans cl ON cl.id = m.clan_id WHERE m.user_id = u.id),
                       (SELECT COALESCE(sum(amount_rub), 0) FROM payments p WHERE p.user_id = u.id),
                       (SELECT count(*) FROM donate_unlocks du WHERE du.user_id = u.id)
                FROM users u
                LEFT JOIN gangs g ON g.user_id = u.id
                LEFT JOIN cities c ON c.id = u.city_id
                WHERE u.id = :u
                """
            ),
            {"u": user_id},
        )
    ).one()
    from bot.services.battle_pass import current_season

    season = await current_season(session)
    bp = await bp_repo.get(session, user_id, season.id)
    return PlayerCard(
        user=user,
        role=await role_of(session, user_id),
        banned=is_banned(user),
        gang=info[0],
        city=info[1],
        districts=info[2],
        clan=info[3],
        resources=await balances(session, user_id),
        paths=await _owned(session, "user_paths", user_id),
        techniques=await _owned(session, "user_techniques", user_id),
        geniuses=await _owned(session, "user_geniuses", user_id),
        bp_level=level_from_xp(bp.xp) if bp else 0,
        bp_premium=bool(bp and bp.is_premium),
        donated_rub=info[4],
        donate_unlocks=info[5],
    )
