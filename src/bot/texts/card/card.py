"""Уникальные персонажи — названия редкостей и позиций, подпись карты (тексты)."""
from __future__ import annotations

from bot.config.card import CardDef
from bot.constant.card import (
    POS_BUSINESSMAN,
    POS_DEFENDER,
    POS_DEPUTY,
    POS_LEADER,
    POS_SCOUT,
    POS_SECURITY,
    POS_SPY,
    POS_TACTICIAN,
    POS_WARLORD,
    RARITY_ABSOLUTE,
    RARITY_BOSS,
    RARITY_GEN_ZERO,
    RARITY_KING,
    RARITY_LEGEND,
    RARITY_MEMBER,
    RARITY_NEW_LEGEND,
    RARITY_PEAK,
    RARITY_STRONG_KING,
)

# Эмодзи редкостей — из 1.0 (игроки к ним привыкли).
RARITY_EMOJI: dict[str, str] = {
    RARITY_MEMBER: "⬜",
    RARITY_BOSS: "🟦",
    RARITY_KING: "🟩",
    RARITY_STRONG_KING: "🟨",
    RARITY_GEN_ZERO: "🟧",
    RARITY_NEW_LEGEND: "🟥",
    RARITY_LEGEND: "💜",
    RARITY_PEAK: "🖤",
    RARITY_ABSOLUTE: "⭐",
}
RARITY_LABELS: dict[str, str] = {
    RARITY_MEMBER: "Член банды",
    RARITY_BOSS: "Глава группировки",
    RARITY_KING: "Король",
    RARITY_STRONG_KING: "Сильный король",
    RARITY_GEN_ZERO: "Нулевое поколение",
    RARITY_NEW_LEGEND: "Новая легенда",
    RARITY_LEGEND: "Легенда",
    RARITY_PEAK: "Вершина",
    RARITY_ABSOLUTE: "Абсолют",
}

POSITION_LABELS: dict[str, str] = {
    POS_LEADER: "👑 Глава",
    POS_DEPUTY: "🎖 Заместитель",
    POS_TACTICIAN: "🧠 Тактик",
    POS_WARLORD: "⚔️ Военачальник",
    POS_BUSINESSMAN: "💼 Бизнесмен",
    POS_SPY: "🕶 Шпион",
    POS_SCOUT: "🔭 Разведка",
    POS_SECURITY: "🛡 Безопасность",
    POS_DEFENDER: "🏰 Защитник",
}
# Что позиция делает — пересказ raw-notes «Уникальные персонажи».
POSITION_DESCRIPTIONS: dict[str, str] = {
    POS_LEADER: "бафы для всей банды",
    POS_DEPUTY: "как глава — бафы для всей банды",
    POS_TACTICIAN: "меньше потерь, больше боевого потенциала, чаще уклонение, блок и контратака",
    POS_WARLORD: "эффект зависит от персонажа",
    POS_BUSINESSMAN: "увеличивает доход и влияет на бизнес",
    POS_SPY: "дебаф противнику перед атакой",
    POS_SCOUT: "данные о противнике",
    POS_SECURITY: "защита от разведки, скрывает данные банды",
    POS_DEFENDER: "участвует, когда бьётся лагерь защиты",
}


def card_label(card: CardDef) -> str:
    """«🟧 Elite (Prime)» — для кнопок (plain text) и строк сообщений."""
    return f"{RARITY_EMOJI[card.rarity]} {card.name}"


def positions_label(positions) -> str:
    return ", ".join(POSITION_LABELS[p] for p in positions) if positions else "—"
