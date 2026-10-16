"""Коллекция уникальных персонажей — список, карточка, распределение (константы)."""
from __future__ import annotations

CB_COLLECTION_OPEN = "coll:open"
CB_COLLECTION_PAGE_PREFIX = "coll:page:"
"""f"{CB_COLLECTION_PAGE_PREFIX}{rarity}:{page}" — карты одной редкости (как в 1.0: сначала
выбор редкости, потом список); без редкости — экран выбора редкости."""
CB_COLLECTION_CARD_PREFIX = "coll:card:"
"""f"{CB_COLLECTION_CARD_PREFIX}{card_code}"."""
CB_COLLECTION_MOVE_PREFIX = "coll:mv:"
"""f"{CB_COLLECTION_MOVE_PREFIX}{card_code}:{from_camp}:{AMOUNT_ONE|AMOUNT_ALL}"."""
CB_COLLECTION_CAMP_MOVE_PREFIX = "coll:cm:"
"""f"{CB_COLLECTION_CAMP_MOVE_PREFIX}{from_camp}:{to_camp}:{percent}" — доля ВСЕХ уников между лагерями."""
CB_COLLECTION_ASSIGN_PREFIX = "coll:asg:"
"""f"{CB_COLLECTION_ASSIGN_PREFIX}{card_code}:{position}"."""

AMOUNT_ONE = "one"
AMOUNT_ALL = "all"
