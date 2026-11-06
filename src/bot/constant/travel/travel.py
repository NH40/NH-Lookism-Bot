"""Переезд (константы)."""
from __future__ import annotations

CB_TRAVEL_OPEN = "travel:open"
CB_TRAVEL_COUNTRIES = "travel:countries"
CB_TRAVEL_CITIES_PREFIX = "travel:cities:"
"""f"{CB_TRAVEL_CITIES_PREFIX}{country_code}:{page}"."""
CB_TRAVEL_PICK_PREFIX = "travel:pick:"
"""f"{CB_TRAVEL_PICK_PREFIX}{city_id}" — город своей страны: сразу, чужой: экран подтверждения."""
CB_TRAVEL_GO_PREFIX = "travel:go:"
"""f"{CB_TRAVEL_GO_PREFIX}{city_id}" — подтверждённая смена страны."""
CB_TRAVEL_ABANDON_ASK = "travel:abandon"
CB_TRAVEL_ABANDON = "travel:abandon:yes"
