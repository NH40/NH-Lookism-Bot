"""Battle Pass (константы) — ветки, callback'и, локи."""
from __future__ import annotations

TRACK_FREE = "free"
TRACK_PREMIUM = "prem"
TRACKS = (TRACK_FREE, TRACK_PREMIUM)

LOCK_ACTION_BP = "bp"

CB_BP_OPEN = "bp:open"
CB_BP_BUY_PREMIUM = "bp:buy"
CB_BP_PAGE_PREFIX = "bp:pg:"  # bp:pg:<страница>
CB_BP_CLAIM_PREFIX = "bp:cl:"  # bp:cl:<ветка>:<уровень>
CB_BP_CLAIM_ALL_PREFIX = "bp:all:"  # bp:all:<ветка>
