"""Магазин (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML.
"""
from __future__ import annotations

SHOP_SCREEN = "🛍 <b>Магазин</b>\n━━━━━━━━━━━━━━━━━━\n🪙 NHCoin: <b>{coins}</b>\n━━━━━━━━━━━━━━━━━━\n{items}"
TRAINER_AVAILABLE = (
    "🥋 <b>Тренер Том Ли</b> — очко мастерства: <b>{price}</b> 🪙\n"
    "📍 Этап «{stage_name}»: куплено <b>{bought}/4</b>\n"
    "🎯 Невложенных: <b>{free}</b>"
)
TRAINER_LOCKED = "🥋 Тренер Том Ли — появится после победы над Томом в задании «Преодоление стены»."
BTN_BUY_POINT = "🥋 Купить очко мастерства — {price} 🪙"
BTN_TO_MASTERY = "🥋 Вложить очки"

# --- popup (без HTML) ---
BOUGHT = "Куплено очко мастерства (−{price} NHCoin). Вложи его в 🥋 Мастерстве."
SOLD_OUT = "Все 4 очка этого этапа уже куплены."
NOT_ENOUGH = "Не хватает NHCoin: нужно {cost}, у тебя {balance}."
TRAINER_LOCKED_ALERT = "Тренер Том Ли откроется после победы над Томом в задании «Преодоление стены»."
BUSY = "Обрабатываю…"
