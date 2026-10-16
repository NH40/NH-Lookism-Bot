"""Ресурсы игрока (тексты): подписи для биржи, казино, ячеек и вкладов."""
from __future__ import annotations

from bot.constant.resource import (
    RES_BLOOD,
    RES_DONATE,
    RES_COINS,
    RES_DEV_POINTS,
    RES_GENIUS_FRAGMENTS,
    RES_PATH_FRAGMENTS,
    RES_PATH_POINTS,
    RES_TECHNIQUE_FRAGMENTS,
    RES_TICKETS,
)

RESOURCE_EMOJI: dict[str, str] = {
    RES_COINS: "🪙",
    RES_TICKETS: "🎟",
    RES_DEV_POINTS: "⭐",
    RES_PATH_POINTS: "🔷",
    RES_PATH_FRAGMENTS: "🛤",
    RES_TECHNIQUE_FRAGMENTS: "🥋",
    RES_GENIUS_FRAGMENTS: "🧠",
    RES_BLOOD: "🩸",
    RES_DONATE: "💎",
}
RESOURCE_NAMES: dict[str, str] = {
    RES_COINS: "NHCoin",
    RES_TICKETS: "Тикеты",
    RES_DEV_POINTS: "Очки развития",
    RES_PATH_POINTS: "Очки пути",
    RES_PATH_FRAGMENTS: "Фрагменты пути",
    RES_TECHNIQUE_FRAGMENTS: "Фрагменты техник",
    RES_GENIUS_FRAGMENTS: "Фрагменты гениальности",
    RES_BLOOD: "Капли крови",
    RES_DONATE: "Донат-коины",
}


def resource_label(code: str) -> str:
    """«🪙 NHCoin» — подпись ресурса для кнопок и текстов."""
    return f"{RESOURCE_EMOJI.get(code, '')} {RESOURCE_NAMES.get(code, code)}".strip()


def amount_label(code: str, amount: int) -> str:
    """«1 500 🪙» — количество с эмодзи ресурса."""
    from bot.utils.formatting import format_number

    return f"{format_number(amount)} {RESOURCE_EMOJI.get(code, '')}".strip()


def item_label(kind: str, code: str) -> str:
    """Подпись предмета (ресурс или отряд статистов) — биржа, ячейки, ставки."""
    from bot.constant.resource import ITEM_RESOURCE
    from bot.texts.gang import squad_title

    if kind == ITEM_RESOURCE:
        return resource_label(code)
    rank, stars, level, school, school_level = code.split(":")
    return "👥 " + squad_title(rank, int(stars), int(level), school, int(school_level))


def item_amount_label(kind: str, code: str, amount: int) -> str:
    """«500 🛤» для ресурса, «1 000 × 👥 C ⭐1» для отряда."""
    from bot.constant.resource import ITEM_RESOURCE
    from bot.utils.formatting import format_number

    if kind == ITEM_RESOURCE:
        return amount_label(code, amount)
    return f"{format_number(amount)} × {item_label(kind, code)}"
