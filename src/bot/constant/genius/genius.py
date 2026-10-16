"""Гениальности (константы). Дизайн — `docs/design/development_systems.md`."""
from __future__ import annotations

GENIUS_BUSINESS = "business"
GENIUS_WAR = "war"
GENIUS_TRAINING = "training"
GENIUS_WEAPONS = "weapons"
GENIUS_MEDIA = "media"
GENIUS_HACKING = "hacking"
GENIUS_OBSERVATION = "observation"
GENIUS_MEDICINE = "medicine"
GENIUS_TACTICS = "tactics"
GENIUS_CHARISMA = "charisma"
GENIUSES: tuple[str, ...] = (
    GENIUS_BUSINESS, GENIUS_WAR, GENIUS_TRAINING, GENIUS_WEAPONS, GENIUS_MEDIA,
    GENIUS_HACKING, GENIUS_OBSERVATION, GENIUS_MEDICINE, GENIUS_TACTICS, GENIUS_CHARISMA,
)

CB_GENIUS_OPEN = "genius:open"
CB_GENIUS_VIEW_PREFIX = "genius:view:"
"""f"{CB_GENIUS_VIEW_PREFIX}{code}"."""
CB_GENIUS_ACTIVATE_PREFIX = "genius:act:"
CB_GENIUS_LEVEL_UP_PREFIX = "genius:up:"
CB_GENIUS_ROLL = "genius:roll"
LOCK_ACTION_GENIUS = "genius"
