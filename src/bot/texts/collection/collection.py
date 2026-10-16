"""Коллекция уникальных персонажей — список, карточка, распределение (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML.
"""
from __future__ import annotations

COLLECTION_HEADER = (
    "🃏 <b>Уникальные персонажи</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🗂 Карт: <b>{cards}</b> · копий: <b>{copies}</b> (в армии {army}, в отряде {placed})\n"
    "⚔️ В атаке: <b>{attack}</b> · 🛡 в защите: <b>{defense}</b>\n"
    "{tickets_line}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Копии вне отряда бьются в армии как статисты и могут погибнуть. Карта на позиции "
    "отряда не сражается и не гибнет — работает навыком позиции.</i>\n\n"
    "<i>Быстро перевести долю уников между лагерями — кнопками ниже.</i>"
)
COLLECTION_EMPTY = (
    "🃏 <b>Уникальные персонажи</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Пока ни одного уника — крути их в 🎯 Вербовке за тикеты.</i>\n"
    "{tickets_line}"
)
CARD_BTN = "{label} ×{total}"
CARDS_MOVED = "Переведено уников: {moved}"
CARDS_NOTHING_TO_MOVE = "Нечего переводить — в этом лагере нет уников (или их слишком мало для этой доли)."
RARITY_BTN = "{emoji} {label} — {cards} · ×{copies}"
RARITY_SCREEN = (
    "{emoji} <b>{label}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🗂 Карт: <b>{cards}</b> · копий: <b>{copies}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Выбери персонажа:</i>"
)
BTN_BACK_TO_RARITIES = "◀️ К редкостям"

CARD_SCREEN = (
    "{label}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "💎 Редкость: <b>{rarity}</b>\n"
    "💪 Мощь одной копии: <b>{power}</b>\n"
    "📌 Позиции: {positions}\n"
    "<i>Навыки: появятся после распределения ролей.</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🗂 Копий: <b>{total}</b>\n"
    "⚔️ В атаке: {attack} · 🛡 В защите: {defense}\n"
    "📌 В отряде: {placed}"
)
BTN_TO_DEFENSE_ONE = "⚔️→🛡 1"
BTN_TO_DEFENSE_ALL = "⚔️→🛡 всех"
BTN_TO_ATTACK_ONE = "🛡→⚔️ 1"
BTN_TO_ATTACK_ALL = "🛡→⚔️ всех"
BTN_ASSIGN = "📌 Поставить: {position}"
BTN_BACK_TO_COLLECTION = "◀️ К коллекции"
BTN_LINEUP = "🏴 Состав отряда"

# --- popup (без HTML) ---
MOVED = "Переведено копий: {moved}"
NOTHING_TO_MOVE = "В этом лагере нет копий этой карты."
CARD_GONE = "Этой карты у тебя больше нет."
ASSIGNED = "{card} — теперь {position}"
ASSIGNED_REPLACED = "{card} — теперь {position}. {old} вернулся в армию."
NO_FREE_COPY = "Свободных копий нет — все в отряде или погибли."
POSITION_NOT_ALLOWED = "Эта карта не может стоять на этой позиции."
