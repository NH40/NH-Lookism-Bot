"""Топ игроков/кланов и награды сезона (конфиг).

Пользователь 2026-10-11: сезон = вайп (патч из админки) и раз в месяц — по итогу сезона
Battle Pass. Топ игроков — по мощи армии. Награды: донат-коины топ-5 игроков
350/300/200/100/80; NHCoin и тикеты — топ-10, «в 10–20 раз меньше и плавнее» первого
черновика (1-е место 1 000 000 🪙 + 100 🎫). Кланы (топ как в поиске — земли, затем
участники): каждому участнику топ-3 — 200/150/100 донат-коинов, топ-4 и топ-5 — NHCoin и тикеты.
"""
from __future__ import annotations

TOP_POWER_REFRESH_SECONDS = 10 * 60  # фоновый пересчёт мощи активных игроков
TOP_POWER_ACTIVE_HOURS = 24  # «активный» — заходил за сутки
TOP_POWER_BATCH = 200  # игроков на одну транзакцию пересчёта
TOP_SEASON_LOOKBACK_DAYS = 3  # сезоны BP, закончившиеся раньше, не выплачиваются задним числом

TOP_PAGE_SIZE = 10
PLAYERS_PAGE_SIZE = 15

# Игроки: место → награда (индекс 0 — 1-е место).
TOP_PLAYER_DONATE: tuple[int, ...] = (350, 300, 200, 100, 80)
TOP_PLAYER_COINS: tuple[int, ...] = (60_000, 54_000, 48_000, 43_000, 38_000, 34_000, 30_000, 26_000, 23_000, 20_000)
TOP_PLAYER_TICKETS: tuple[int, ...] = (8, 7, 7, 6, 6, 5, 5, 4, 4, 3)

# Кланы: каждому участнику клана на этом месте.
TOP_CLAN_DONATE: tuple[int, ...] = (200, 150, 100)
TOP_CLAN_COINS: tuple[int, ...] = (0, 0, 0, 20_000, 15_000)
TOP_CLAN_TICKETS: tuple[int, ...] = (0, 0, 0, 3, 2)


def _at(table: tuple[int, ...], place: int) -> int:
    return table[place - 1] if 1 <= place <= len(table) else 0


def player_reward(place: int) -> tuple[int, int, int]:
    """→ (донат-коины, NHCoin, тикеты) за место `place` (1…) в топе игроков."""
    return _at(TOP_PLAYER_DONATE, place), _at(TOP_PLAYER_COINS, place), _at(TOP_PLAYER_TICKETS, place)


def clan_reward(place: int) -> tuple[int, int, int]:
    """→ (донат-коины, NHCoin, тикеты) каждому участнику клана на месте `place`."""
    return _at(TOP_CLAN_DONATE, place), _at(TOP_CLAN_COINS, place), _at(TOP_CLAN_TICKETS, place)


TOP_PLAYER_PLACES = max(len(TOP_PLAYER_DONATE), len(TOP_PLAYER_COINS), len(TOP_PLAYER_TICKETS))
TOP_CLAN_PLACES = max(len(TOP_CLAN_DONATE), len(TOP_CLAN_COINS), len(TOP_CLAN_TICKETS))
