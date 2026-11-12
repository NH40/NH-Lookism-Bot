"""Предупреждение о нападении на соклановца (пользователь 2026-11-12: «чтобы соклановцы не
дрались друг с другом по незнанию»). Не запрет — подтверждение: бот показывает экран «это твой
соклановец», Mini App переспрашивает (`api/routers/_common.require_clanmate_confirm`)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CONFIRM_SUFFIX = ":cm"  # к callback_data: игрок уже подтвердил


async def clanmate_name(session: AsyncSession, attacker_id: int, target_id: int | None) -> str | None:
    """Имя цели, если она в том же клане, что нападающий; иначе None."""
    if not target_id or target_id == attacker_id:
        return None
    return await session.scalar(text(
        "SELECT COALESCE(u.display_name, u.username, 'игрок') FROM clan_members a "
        "JOIN clan_members b ON b.clan_id = a.clan_id AND b.user_id = :t "
        "JOIN users u ON u.id = :t WHERE a.user_id = :a"
    ), {"a": attacker_id, "t": target_id})


def split_confirm(data: str) -> tuple[str, bool]:
    """callback_data без суффикса подтверждения + подтверждено ли."""
    if data.endswith(CONFIRM_SUFFIX):
        return data[: -len(CONFIRM_SUFFIX)], True
    return data, False


async def district_owner(session: AsyncSession, district_id: int) -> int | None:
    return await session.scalar(text("SELECT owner_id FROM districts WHERE id = :d"), {"d": district_id})


async def city_emperor(session: AsyncSession, user_id: int) -> int | None:
    """Император города игрока (цель саботажа)."""
    return await session.scalar(text(
        "SELECT c.emperor_id FROM users u JOIN cities c ON c.id = u.city_id WHERE u.id = :u"
    ), {"u": user_id})
