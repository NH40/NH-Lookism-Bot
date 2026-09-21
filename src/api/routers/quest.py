"""API-роутер Mini App для домена quest.

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: упомянут в навигации, содержание не описано. Бизнес-логика — ТОЛЬКО через
bot.services.quest (тот же сервис, что вызывает и bot.handlers.quest) — роутер
не дублирует и не переизобретает правила, только валидирует initData/парсит запрос
(см. CLAUDE.md, «Mini App» — единая точка бизнес-логики для бота и Mini App).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user_id

router = APIRouter(prefix="/api/quest", tags=["quest"])
