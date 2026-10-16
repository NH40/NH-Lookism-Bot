"""Уникальные персонажи — редкости, позиции отряда (константы).

Модель подтверждена пользователем 2026-09-30 (см. `docs/design/unique_characters.md`,
раздел 0): без пыли/звёзд/уровней; карта вне отряда — боец армии (стопка по лагерям, как
статисты), карта на позиции — не бьётся и не гибнет, работает навыком позиции; одна копия —
одна позиция. Коды хранятся в БД и сравниваются — константы, не литералы.
"""
from __future__ import annotations

# Редкости — от слабейшей к сильнейшей (порядок важен: сортировка коллекции).
RARITY_MEMBER = "member"
RARITY_BOSS = "boss"
RARITY_KING = "king"
RARITY_STRONG_KING = "strong_king"
RARITY_GEN_ZERO = "gen_zero"
RARITY_NEW_LEGEND = "new_legend"
RARITY_LEGEND = "legend"
RARITY_PEAK = "peak"
RARITY_ABSOLUTE = "absolute"

RARITY_ORDER: tuple[str, ...] = (
    RARITY_MEMBER,
    RARITY_BOSS,
    RARITY_KING,
    RARITY_STRONG_KING,
    RARITY_GEN_ZERO,
    RARITY_NEW_LEGEND,
    RARITY_LEGEND,
    RARITY_PEAK,
    RARITY_ABSOLUTE,
)
RARITY_INDEX: dict[str, int] = {r: i for i, r in enumerate(RARITY_ORDER)}

# 9 позиций отряда (raw-notes «Банда»), в порядке показа.
POS_LEADER = "leader"
POS_DEPUTY = "deputy"
POS_TACTICIAN = "tactician"
POS_WARLORD = "warlord"
POS_BUSINESSMAN = "businessman"
POS_SPY = "spy"
POS_SCOUT = "scout"
POS_SECURITY = "security"
POS_DEFENDER = "defender"

POSITIONS: tuple[str, ...] = (
    POS_LEADER,
    POS_DEPUTY,
    POS_TACTICIAN,
    POS_WARLORD,
    POS_BUSINESSMAN,
    POS_SPY,
    POS_SCOUT,
    POS_SECURITY,
    POS_DEFENDER,
)
