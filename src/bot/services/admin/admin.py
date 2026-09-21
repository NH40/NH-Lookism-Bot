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
from bot.db.repositories.user import get_by_id


async def is_admin(session: AsyncSession, user_id: int, settings: Settings) -> bool:
    if user_id in settings.admin_ids:
        return True
    user = await get_by_id(session, user_id)
    return user is not None and user.is_admin
