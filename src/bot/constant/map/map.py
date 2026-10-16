"""Карта — город игрока и его районы (константы)."""
from __future__ import annotations

CB_MAP_OPEN = "map:open"
CB_MAP_PAGE_PREFIX = "map:page:"
# Карта страны (круг и выше) — города страны и экран одного города со списком владельцев.
CB_MAP_COUNTRY_PAGE_PREFIX = "map:country:"
"""f"{CB_MAP_COUNTRY_PAGE_PREFIX}{page}"."""
CB_MAP_CITY_PREFIX = "map:city:"
"""f"{CB_MAP_CITY_PREFIX}{city_id}:{page}" — владельцы районов города."""
