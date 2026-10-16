"""Районы — карточка района, атака (константы)."""
from __future__ import annotations

CB_DISTRICT_VIEW_PREFIX = "district:view:"
CB_DISTRICT_ATTACK_PREFIX = "district:attack:"
CB_CHALLENGE_ACCEPT_PREFIX = "district:accept:"
# Круг: бой за город (с каждым владельцем отдельно — подтверждено 2026-09-29).
CB_CITY_ATTACK_BOTS_PREFIX = "district:citybots:"
"""f"{CB_CITY_ATTACK_BOTS_PREFIX}{city_id}" — один бой против всех ботов города."""
CB_CITY_CHALLENGE_PREFIX = "district:citych:"
"""f"{CB_CITY_CHALLENGE_PREFIX}{city_id}:{owner_id}" — вызов за все районы игрока в городе."""

# Вызов на район игрока (PvP) — статус и исход сравниваются (фильтр висящих вызовов,
# частичные уникальные индексы) — константы, не литералы.
CHALLENGE_PENDING = "pending"
CHALLENGE_RESOLVED = "resolved"

RESOLUTION_ACCEPTED = "accepted"  # защитник принял — бьётся лагерем атаки
RESOLUTION_TIMEOUT = "timeout"  # не ответил за час — бьётся лагерь защиты
RESOLUTION_VOID = "void"  # к моменту боя район уже не принадлежит защитнику — боя нет

# Масштаб вызова: один район (банда) или все районы защитника в городе (круг).
SCOPE_DISTRICT = "district"
SCOPE_CITY = "city"
