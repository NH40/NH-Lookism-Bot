"""PvP-покер (константы)."""
from __future__ import annotations

TABLE_WAITING = "waiting"
TABLE_ACTIVE = "active"
TABLE_FINISHED = "finished"
TABLE_CANCELLED = "cancelled"

PLAYER_ACTIVE = "active"
PLAYER_FOLDED = "folded"
PLAYER_ALL_IN = "all_in"

STREETS: tuple[str, ...] = ("preflop", "flop", "turn", "river")
STREET_SHOWDOWN = "showdown"

ACT_FOLD = "fold"
ACT_CHECK = "check"
ACT_CALL = "call"
ACT_RAISE = "raise"

CB_POKER_OPEN = "poker:open"
CB_POKER_CREATE = "poker:new"  # выбор бай-ина
CB_POKER_CREATE_PREFIX = "poker:mk:"  # f"{...}{buy_in}" | f"{...}{buy_in}:{players}" | f"{...}{buy_in}:{players}:{wait}"
CB_POKER_JOIN_PREFIX = "poker:join:"  # f"{...}{table_id}"
CB_POKER_VIEW_PREFIX = "poker:view:"  # f"{...}{table_id}" — экран стола
CB_POKER_LEAVE_PREFIX = "poker:leave:"  # f"{...}{table_id}"
CB_POKER_ACT_PREFIX = "poker:act:"  # f"{...}{table_id}:{hand_no}:{action}:{amount}"
