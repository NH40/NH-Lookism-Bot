"""Ячейки хранения (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

STORAGE_SCREEN = (
    "🗄 <b>Ячейки хранения</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🛡 Что лежит в ячейке, то в безопасности: его не украсть саботажем, не забрать войной и не "
    "потерять в бою. Сгорает содержимое только при пробуждении и удалении банды.\n"
    "💸 Хранение: <b>{fee}</b> 🪙 в час за непустую ячейку — плата копится и платится, когда достаёшь.\n━━━━━━━━━━━━━━━━━━\n"
    "{cells}"
)
CELL_LINE_ITEM = "📦 <b>{n}.</b> {item} — <b>{amount}</b>{debt}\n"
CELL_LINE_EMPTY = "▫️ <b>{n}.</b> <i>пусто</i>\n"
CELL_LINE_LOCKED = "🔒 <b>{n}.</b> закрыта — {cost} 🪙\n"
CELL_DEBT = " · долг {debt} 🪙"
BTN_CELL = "🗄 {n} · {item}"
BTN_CELL_EMPTY = "🗄 {n} · пусто"
BTN_UNLOCK = "🔓 Открыть ячейку {n} · {cost} 🪙"
BTN_STORAGE = "🗄 Ячейки"

CELL_SCREEN_EMPTY = "🗄 <b>Ячейка {n}</b> — пусто\n━━━━━━━━━━━━━━━━━━\n<i>Что положить?</i>"
CELL_SCREEN_ITEM = (
    "🗄 <b>Ячейка {n}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "📦 Лежит: <b>{item}</b> — <b>{amount}</b>\n"
    "💸 Долг за хранение: <b>{debt}</b> 🪙\n"
    "<i>Платится, когда достаёшь.</i>"
)
BTN_PUT_STATISTS = "👥 Статистов"
BTN_TAKE_ALL = "📤 Достать всё"
BTN_TAKE_PART = "📤 Достать часть"
BTN_TOPUP = "➕ Доложить"

PICK_SQUAD = "👥 <b>Какой отряд положить в ячейку {n}?</b>\n━━━━━━━━━━━━━━━━━━\n<i>Бойцы берутся сначала из защиты, потом из атаки.</i>"
PICK_SQUAD_NONE = "У тебя нет статистов."
BTN_SQUAD = "{title} · {total}"

AMOUNT_PUT = "📥 Сколько положить: <b>{item}</b>?\n👛 У тебя: <b>{have}</b>\n<i>Напиши число.</i>"
AMOUNT_TAKE = "📤 Сколько достать: <b>{item}</b>?\n🗄 В ячейке: <b>{have}</b>\n<i>Напиши число.</i>"
AMOUNT_INVALID = "Нужно целое число больше нуля. Попробуй ещё раз."

STORED = "🗄 В ячейке <b>{n}</b>: {item} — <b>{amount}</b>"
TAKEN = "📤 Достал: {item} — <b>{amount}</b>{paid}"
TAKEN_PAID = "\n💸 Плата за хранение: <b>{debt}</b> 🪙"

# --- popup (без HTML) ---
OPENED_ALERT = "Ячейка {n} открыта (−{cost} NHCoin)"
LOCKED_ALERT = "Эта ячейка ещё закрыта — открывай по порядку."
OCCUPIED_ALERT = "В ячейке лежит другая вещь — сначала достань её."
EMPTY_ALERT = "Ячейка пуста."
NOT_ENOUGH_ALERT = "Столько нет."
NOT_ENOUGH_COINS_ALERT = "Не хватает NHCoin: нужно {cost}."
BUSY_ALERT = "Обрабатываю…"
