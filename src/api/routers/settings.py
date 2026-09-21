"""API-роутер Mini App для домена settings.

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: —. Бизнес-логика — ТОЛЬКО через
bot.services.settings (тот же сервис, что вызывает и bot.handlers.settings) — роутер
не дублирует и не переизобретает правила, только валидирует initData/парсит запрос
(см. CLAUDE.md, «Mini App» — единая точка бизнес-логики для бота и Mini App).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user_id

router = APIRouter(prefix="/api/settings", tags=["settings"])
