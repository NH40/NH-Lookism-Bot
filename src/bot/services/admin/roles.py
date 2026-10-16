"""Роли админки и права разделов (сервис). Супер-админ — ADMIN_IDS из .env (проверка без БД),
остальные роли — `users.admin_role` (выдаёт и снимает супер-админ, раздел «Роли»)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.admin import ROLE_LEVEL, SECTION_MIN_ROLE, SECTION_ORDER
from bot.config.settings import get_settings
from bot.constant.admin import ROLE_SUPER, ROLES


async def role_of(session: AsyncSession, user_id: int) -> str | None:
    if user_id in get_settings().admin_ids:
        return ROLE_SUPER
    role = (
        await session.execute(
            text("SELECT COALESCE(admin_role, CASE WHEN is_admin THEN 'admin' END) FROM users WHERE id = :u"),
            {"u": user_id},
        )
    ).scalar_one_or_none()
    return role if role in ROLES else None


def allowed(role: str | None, section: str) -> bool:
    return role is not None and ROLE_LEVEL[role] >= ROLE_LEVEL[SECTION_MIN_ROLE[section]]


async def can(session: AsyncSession, user_id: int, section: str) -> bool:
    return allowed(await role_of(session, user_id), section)


def visible_sections(role: str | None) -> list[str]:
    return [s for s in SECTION_ORDER if allowed(role, s)]


async def set_role(session: AsyncSession, user_id: int, role: str | None) -> bool:
    """Выдать/снять роль (None — снять, включая legacy `is_admin`). НЕ коммитит."""
    if role is not None and role not in ROLES:
        raise ValueError(role)
    result = await session.execute(
        text("UPDATE users SET admin_role = :r, is_admin = false WHERE id = :u"), {"u": user_id, "r": role}
    )
    return result.rowcount > 0


async def list_staff(session: AsyncSession) -> list[tuple[int, str | None, str]]:
    """[(id, @ник, роль)] всех с ролью в БД."""
    rows = await session.execute(
        text(
            "SELECT id, username, COALESCE(admin_role, 'admin') FROM users "
            "WHERE admin_role IS NOT NULL OR is_admin ORDER BY id"
        )
    )
    return [tuple(r) for r in rows.all()]
