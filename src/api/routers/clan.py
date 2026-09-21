"""API-роутер Mini App для домена clan.

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: упомянут в профиле/навигации, содержание не описано. Бизнес-логика — ТОЛЬКО через
bot.services.clan (тот же сервис, что вызывает и bot.handlers.clan) — роутер
не дублирует и не переизобретает правила, только валидирует initData/парсит запрос
(см. CLAUDE.md, «Mini App» — единая точка бизнес-логики для бота и Mini App).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user_id

router = APIRouter(prefix="/api/clan", tags=["clan"])
