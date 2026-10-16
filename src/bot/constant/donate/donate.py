"""Донат (константы): виды покупок чёрного рынка, callback'и, локи."""
from __future__ import annotations

KIND_GENIUS = "genius"
KIND_PATH = "path"
KIND_TECHNIQUE = "tech"
DONATE_KINDS = (KIND_GENIUS, KIND_PATH, KIND_TECHNIQUE)

LOCK_ACTION_DONATE = "donate"
PAYLOAD_DONATE_PREFIX = "donate:"  # payload инвойса: donate:<рубли>

CB_DONATE_OPEN = "dn:open"
CB_DONATE_PRESET_PREFIX = "dn:pay:"  # dn:pay:<рубли>
CB_DONATE_CUSTOM = "dn:custom"
CB_MARKET_OPEN = "bm:open"
CB_MARKET_BODY = "bm:body"
CB_MARKET_BODY_BUY = "bm:body:ok"
CB_MARKET_KIND_PREFIX = "bm:k:"  # bm:k:<вид>
CB_MARKET_ITEM_PREFIX = "bm:i:"  # bm:i:<вид>:<код>
CB_MARKET_UNLOCK_PREFIX = "bm:u:"  # bm:u:<вид>:<код>
CB_MARKET_LEVEL_PREFIX = "bm:l:"  # bm:l:<вид>:<код>
