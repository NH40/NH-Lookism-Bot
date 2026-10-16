"""Админ-панель (сервис).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md` — пока в сырых
заметках 2.0 нет отдельного раздела про админку, переносить/додумывать состав команд
по мере необходимости, уточняя через AskUserQuestion. Пока — только `is_admin`, нужен
middlewares/tech_mode и filters/admin (права = конфиг ИЛИ БД, с коротким замыканием —
см. CLAUDE.md, "Админ-панель").
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings


async def is_admin(session: AsyncSession, user_id: int, settings: Settings) -> bool:
    """Любая роль админки (супер — ADMIN_IDS; остальные — `users.admin_role`, см. `roles`)."""
    if user_id in settings.admin_ids:
        return True
    from bot.services.admin.roles import role_of

    return await role_of(session, user_id) is not None

