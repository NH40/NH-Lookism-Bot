"""Вербовка — статисты (по влиянию, КД 20 минут) и уникальные персонажи (за тикеты) (тексты)."""
from __future__ import annotations

RECRUIT_MENU_HEADER = (
    "🎯 <b>Вербовка</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{army_block}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🗣 Влияние: <b>{influence}</b> · за раз: <b>{crowd}</b> бойцов, отбор: <b>{select}</b> · потолок ранга: <b>{ceiling}</b>\n"
    "{tickets_line}\n"
    "<i>Уникальные персонажи — за тикеты: чем выше редкость, тем реже выпадает.</i>"
)

RECRUIT_RESULT = "✅ Завербовано бойцов: <b>{count}</b>. Лучший ранг: <b>{rank}</b> (мощь {power}).\n{ranks}"
RECRUIT_RANK_ITEM = "{rank} × {count}"
BTN_RECRUIT_CROWD = "🎯 Завербовать: {count} бойцов"
BTN_RECRUIT_SELECT = "🎖 Отбор: {count}, только сильные ранги"

RECRUIT_COOLDOWN = "⏳ Вербовка ещё на кулдауне — попробуй через {countdown}."
