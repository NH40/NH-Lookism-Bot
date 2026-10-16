"""Контракты статистов (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

CONTRACT_SCREEN = (
    "📜 <b>Контракты статистов</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🪖 Наёмники встают в лагерь атаки на {hours} ч, воюют и гибнут как свои, но не тренируются. "
    "Погибли — это твоя потеря, деньги не возвращаются.\n━━━━━━━━━━━━━━━━━━\n"
    "👑 Твой потолок по влиянию: <b>{ceiling}</b>\n"
    "<i>Выбери ранг — цена за одного бойца на срок:</i>"
    "{active}"
)
CONTRACT_DISCOUNT_LINE = "\n🩸 Скидка Джинчоля: −{percent}%"
CONTRACT_ACTIVE_HEAD = "\n━━━━━━━━━━━━━━━━━━\n🪖 <b>Сейчас наняты:</b>"
CONTRACT_ACTIVE_LINE = "\n   🔹 {quantity} × {rank} — ещё {countdown}"
BTN_CONTRACT_RANK = "{rank} · {price} 🪙"
BTN_CONTRACT_PREV = "◀️ Сильнее"
BTN_CONTRACT_NEXT = "Слабее ▶️"
BTN_CONTRACTS = "📜 Контракты статистов"

QUANTITY_PROMPT = (
    "📜 <b>Наём: ранг {rank}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "💪 Мощь бойца: <b>{power}</b>\n"
    "💰 Цена: <b>{price}</b> 🪙 за одного на {hours} ч\n"
    "👛 У тебя {coins} 🪙 — хватит на <b>{affordable}</b> бойцов\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Сколько нанять? Напиши число.</i>"
)
QUANTITY_INVALID = "Нужно целое число больше нуля (не больше {max}). Попробуй ещё раз."
QUOTE_SCREEN = (
    "📜 <b>Подтверди найм</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🪖 {quantity} × {rank} на {hours} ч\n"
    "💪 Мощь отряда: <b>{power}</b>\n"
    "💰 Цена: <b>{total} 🪙</b> ({price} 🪙 за бойца)\n"
    "👛 У тебя: {coins} 🪙"
)
BTN_CONFIRM_BUY = "✅ Нанять за {total} 🪙"

# --- popup (без HTML) ---
BOUGHT_ALERT = "Наёмники в строю: {quantity} × {rank} на {hours} ч"
NOT_ENOUGH_ALERT = "Не хватает NHCoin: нужно {cost}."
RANK_LOCKED_ALERT = "Этот ранг выше твоего потолка по влиянию."
BUSY_ALERT = "Обрабатываю…"
