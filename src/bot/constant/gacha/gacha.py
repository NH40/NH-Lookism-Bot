"""Крутки за тикеты — получение уникального персонажа (константы)."""
from __future__ import annotations

CB_GACHA_ROLL = "gacha:roll"
CB_GACHA_ROLL_MANY = "gacha:many"  # дальше — ввод количества (GachaStates.waiting_count)
# Правило 2: Redis-лок на крутку — ключ по user_id + это действие.
LOCK_ACTION_ROLL = "roll"
