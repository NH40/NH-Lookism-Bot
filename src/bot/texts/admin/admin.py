"""Админ-панель и бета-режим (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML (Telegram не парсит разметку в popup).
"""
from __future__ import annotations

from bot.config.admin import BETA_CODE_MAX_LENGTH, BETA_CODE_MIN_LENGTH

PANEL = "🛠 <b>Админ-панель</b>\n━━━━━━━━━━━━━━━━━━\n{beta_block}\n━━━━━━━━━━━━━━━━━━\n🛠 Техрежим: {tech}"
BETA_ON_BLOCK = (
    "🧪 Бета-режим: 🟢 включён\n"
    "🔑 Код: <code>{code}</code>\n"
    "👥 Допущено игроков: <b>{allowed}</b>\n"
    "<i>Все, кроме админов, перед игрой вводят этот код.</i>"
)
BETA_OFF_BLOCK = "🧪 Бета-режим: 🔴 выключен — бот открыт всем."
TECH_ON = "🟢 включён (бот закрыт для всех, кроме админов)"
TECH_OFF = "🔴 выключен"

BTN_BETA_ON = "🧪 Включить бета-режим"
BTN_BETA_CODE = "🔑 Сменить код"
BTN_BETA_OFF = "🧪 Выключить бета-режим"
BTN_TECH_ON = "🛠 Включить техрежим"
BTN_TECH_OFF = "🛠 Выключить техрежим"
BTN_GENERATE = "🎲 Сгенерировать"
BTN_BACK = "◀️ Назад"
BTN_CONFIRM_OFF = "✅ Да, выключить"

CODE_PROMPT_ENABLE = (
    "🧪 <b>Включение бета-режима</b>\n━━━━━━━━━━━━━━━━━━\n"
    f"Пришли кодовое слово для этой беты ({BETA_CODE_MIN_LENGTH}–{BETA_CODE_MAX_LENGTH} символов, "
    "регистр не важен) или нажми «🎲 Сгенерировать».\n\n"
    "Игроки, которые уже в боте, тоже должны будут ввести код."
)
CODE_PROMPT_CHANGE = (
    "🔑 <b>Новый код беты</b>\n━━━━━━━━━━━━━━━━━━\n"
    f"Пришли новое кодовое слово ({BETA_CODE_MIN_LENGTH}–{BETA_CODE_MAX_LENGTH} символов) или нажми "
    "«🎲 Сгенерировать».\n\nУже допущенные игроки доступ НЕ теряют — новый код нужен только новым."
)
CODE_TOO_SHORT = f"Слишком коротко — минимум {BETA_CODE_MIN_LENGTH} символа. Пришли другое слово:"
CODE_TOO_LONG = f"Слишком длинно — максимум {BETA_CODE_MAX_LENGTH} символов. Пришли другое слово:"

BETA_ENABLED = "✅ Бета-режим включён. Код: <code>{code}</code> — раздай его тестерам."
BETA_CODE_CHANGED = "✅ Новый код беты: <code>{code}</code>"
OFF_CONFIRM = (
    "🧪 <b>Выключить бета-режим?</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Бот откроется всем. Допуски всех {allowed} игроков сбросятся — при следующем включении "
    "беты им понадобится новый код."
)
BETA_DISABLED = "✅ Бета-режим выключен, бот открыт всем. Сброшено допусков: {allowed}."

# --- popup (без HTML) ---
BETA_ALREADY_ON = "Бета уже включена."
BETA_ALREADY_OFF = "Бета уже выключена."
TECH_TOGGLED_ON = "Техрежим включён."
TECH_TOGGLED_OFF = "Техрежим выключен."

# --- экран игрока, пока бета закрыта ---
BETA_GATE_PROMPT = (
    "🧪 <b>Бот в режиме бета-теста</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🔑 Чтобы играть, пришли кодовое слово.\n<i>Его выдаёт администратор.</i>"
)
BETA_GATE_WRONG = "❌ Неверное кодовое слово. Попробуй ещё раз или спроси код у администратора."
BETA_GATE_LOCKED = "⛔ Слишком много неверных попыток. Попробуй позже."
BETA_GATE_GRANTED = "✅ Доступ к бете открыт! Нажми /start, чтобы начать."
BETA_GATE_ALERT = "Бот в режиме бета-теста — пришли кодовое слово в чат."


# --- Админ-система 2.0 ---
from bot.constant.admin import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_MODERATOR,
    ROLE_SUPER,
    ROLE_SUPPORT,
    SECTION_CLANS,
    SECTION_CONFIG,
    SECTION_EVENTS,
    SECTION_LOGS,
    SECTION_MASS,
    SECTION_PATCH,
    SECTION_PLAYERS,
    SECTION_PROMO,
    SECTION_REFERRAL,
    SECTION_ROLES,
    SECTION_SEASON,
    SECTION_STATS,
    SECTION_SYSTEM,
    SECTION_WORLD,
)

MAIN_PANEL = (
    "🛠 <b>Админ-панель</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "👤 Роль: <b>{role}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Выбери раздел:</i>"
)
ROLE_NAMES = {ROLE_SUPER: "👑 Супер-админ", ROLE_ADMIN: "🛡 Админ", ROLE_MODERATOR: "⚖️ Модератор", ROLE_SUPPORT: "💬 Саппорт"}
SECTION_TITLES = {
    SECTION_PLAYERS: "👤 Игроки",
    SECTION_MASS: "📢 Рассылка",
    SECTION_PROMO: "🎟 Промокоды",
    SECTION_STATS: "📊 Статистика",
    SECTION_LOGS: "📜 Журналы",
    SECTION_WORLD: "🗺 Мир",
    SECTION_EVENTS: "🎉 События",
    SECTION_CLANS: "🏰 Кланы",
    SECTION_SEASON: "🎫 Пасс и задания",
    SECTION_REFERRAL: "🔗 Рефералы",
    SECTION_ROLES: "👑 Роли",
    SECTION_PATCH: "💣 Патч и вайп",
    SECTION_CONFIG: "⚙️ Настройки",
    SECTION_SYSTEM: "🧪 Бета и техрежим",
}
SECTION_STUB = "{title}\n━━━━━━━━━━━━━━━━━━\n<i>Раздел в разработке.</i>"
NO_RIGHTS_ALERT = "Недостаточно прав для этого раздела."

FIND_PROMPT = "👤 <b>Поиск игрока</b>\nПришли <b>@ник</b> или <b>id</b> игрока:"
FIND_NOT_FOUND = "❌ Игрок «{query}» не найден. Пришли другой @ник или id:"
PLAYER_NOT_FOUND_ALERT = "Игрок не найден."
PLAYER_CARD = (
    "👤 <b>{name}</b> · <code>{id}</code>{username}\n"
    "{role}{ban}"
    "━━━━━━━━━━━━━━━━━━\n"
    "🏴 Банда: <b>{gang}</b> · 🏙 {city} · 📍 районов: <b>{districts}</b>\n"
    "🏰 Клан: <b>{clan}</b>\n"
    "🕒 Последняя активность: {last_active}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<b>Ресурсы</b>\n{resources}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<b>Развитие</b>\n"
    "🩸 Родословная: {bloodline}\n"
    "🛤 Пути: {paths}\n"
    "🥋 Техники: {techniques}\n"
    "🧠 Гении: {geniuses}\n"
    "🌅 Пробуждение: <b>{awakening}</b> · потенциал: <b>{potential}</b>\n"
    "🧍 Второе тело: {body}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🎫 Пасс: ур. <b>{bp_level}</b>{bp_premium}\n"
    "💳 Задонатил: <b>{donated}</b> ₽ · покупок чёрного рынка: <b>{unlocks}</b>"
)
CARD_ROLE = "🛡 Роль: <b>{role}</b>\n"
CARD_BAN_FOREVER = "⛔️ <b>Забанен навсегда</b>{reason}\n"
CARD_BAN_UNTIL = "⛔️ <b>Забанен до {until}</b>{reason}\n"
CARD_BAN_REASON = " — {reason}"
CARD_NONE = "—"
CARD_PREMIUM = " · 💎 премиум"
BTN_PLAYER_GIVE = "💰 Выдать/забрать"
BTN_PLAYER_DEV = "🌀 Развитие"
BTN_PLAYER_PUNISH = "⛔️ Наказания"
BTN_PLAYER_LOG = "📜 Журнал"
BTN_REFRESH = "🔄 Обновить"
BTN_FIND_ANOTHER = "🔍 Другой игрок"
BTN_BACK_TO_PLAYER = "◀️ К игроку"

# --- задания игрока (2026-10-12) ---
BTN_PLAYER_QUESTS = "📅 Задания"
QUESTS_SCREEN = (
    "📅 <b>Задания игрока</b> {name}\n━━━━━━━━━━━━━━━━━━\n"
    "<b>Ежедневные</b> (опыт пасса начислится как обычно):\n{daily}\n\n"
    "<b>Квесты развития</b> (награду игрок заберёт на экране системы):\n{dev}"
)
QUESTS_NONE = "<i>нет невыполненных</i>"
QUEST_DAILY_LINE = "▫️ {label}: {progress}/{target}"
QUEST_DEV_LINE = "▫️ {title}"
BTN_QUEST_DAILY = "✅ {label}"
BTN_QUEST_DEV = "✅ {title}"
BTN_QUEST_ALL = "✅ Засчитать все"
QUESTS_DONE_ALERT = "Засчитано: ежедневных {daily}, квестов развития {dev}."
QUEST_GONE_ALERT = "Это задание уже выполнено."
