"""Вклады (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

DEPOSIT_SCREEN = (
    "🏦 <b>Вклады</b>\n━━━━━━━━━━━━━━━━━━\n"
    "💡 Положи ресурс на срок — по сроку заберёшь его с процентами. Досрочно — только то, что "
    "положил. Вклады не на балансе: саботажу и войне до них не добраться. До {max} вкладов сразу.\n━━━━━━━━━━━━━━━━━━\n"
    "{rows}"
)
DEPOSIT_ROW_READY = "✅ <b>#{id}</b> · {amount} → <b>{payout}</b> — готов\n"
DEPOSIT_ROW_WAIT = "⏳ <b>#{id}</b> · {amount} → {payout} — ещё {countdown}\n"
DEPOSIT_NONE = "📭 <i>Вкладов нет.</i>"
BTN_NEW_DEPOSIT = "➕ Открыть вклад"
BTN_CLAIM_READY = "💰 Забрать #{id} · {payout}"
BTN_CLAIM_EARLY = "↩️ Досрочно #{id} (без %)"
BTN_DEPOSITS = "🏦 Вклады"

PICK_RESOURCE = "🏦 <b>Что положить во вклад?</b>"
PICK_TERM = (
    "🏦 <b>Вклад: {resource}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "📏 Потолок одного вклада: <b>{cap}</b>\n"
    "<i>Выбери срок:</i>"
)
BTN_TERM = "{hours} ч · +{percent}%"
AMOUNT_PROMPT = (
    "🏦 <b>Вклад: {resource} на {hours} ч, +{percent}%</b>\n━━━━━━━━━━━━━━━━━━\n"
    "👛 У тебя: <b>{have}</b> · 📏 потолок: <b>{cap}</b>\n"
    "<i>Сколько положить? Напиши число.</i>"
)
AMOUNT_INVALID = "Нужно целое число от 1 до {cap}. Попробуй ещё раз."
OPENED = "🏦 Вклад <b>#{id}</b> открыт\n━━━━━━━━━━━━━━━━━━\n💰 {amount} на {hours} ч → заберёшь <b>{payout}</b>"

# --- popup (без HTML) ---
CLAIMED_ALERT = "Получено: {amount}"
CLAIMED_EARLY_ALERT = "Возвращено без процентов: {amount}"
TOO_MANY_ALERT = "Уже {max} вклада — забери какой-нибудь."
NOT_ENOUGH_ALERT = "Столько нет."
NOT_FOUND_ALERT = "Вклад уже забран."
BUSY_ALERT = "Обрабатываю…"
