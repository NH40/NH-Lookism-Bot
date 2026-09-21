"""API-роутер Mini App для домена boss.

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Развитие» — упомянуты в списке из 4 событий, детали не описаны. Бизнес-логика — ТОЛЬКО через
bot.services.boss (тот же сервис, что вызывает и bot.handlers.boss) — роутер
не дублирует и не переизобретает правила, только валидирует initData/парсит запрос
(см. CLAUDE.md, «Mini App» — единая точка бизнес-логики для бота и Mini App).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user_id

router = APIRouter(prefix="/api/boss", tags=["boss"])
