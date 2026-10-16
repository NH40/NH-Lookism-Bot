"""Топ игроков/кланов и список игроков (константы)."""
from __future__ import annotations

TAB_PLAYERS = "p"
TAB_CLANS = "c"

CB_TOP_PREFIX = "top:"
"""f"{CB_TOP_PREFIX}{TAB_PLAYERS|TAB_CLANS}" — экран топа."""
CB_PLAYERS_PAGE_PREFIX = "players:"
"""f"{CB_PLAYERS_PAGE_PREFIX}{page}" — список всех игроков."""

PAYOUT_KEY_BP = "bp:{number}"
PAYOUT_KEY_PATCH = "patch:{stamp}"
