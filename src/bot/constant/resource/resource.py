"""Ресурсы игрока (константы) — единые коды для биржи, казино, ячеек хранения и вкладов.

Пользователь 2026-10-04: на бирже торгуются «все ресурсы, что есть в игре, включая донат»,
в казино ставят «любым ресурсом (как в 1.0)». Коды сравниваются и уходят в `callback_data`
и в строки БД (лоты биржи, вклады, ячейки) — поэтому константы, не литералы. Донат-коины
(`RES_DONATE`) — тоже здесь, но без вкладов и казино (`NO_MINT_RESOURCES`).
"""
from __future__ import annotations

RES_COINS = "coins"  # NHCoin
RES_TICKETS = "tickets"
RES_DEV_POINTS = "dev_pts"  # очки развития (характеристики)
RES_PATH_POINTS = "path_pts"  # очки пути
RES_PATH_FRAGMENTS = "path_fr"
RES_TECHNIQUE_FRAGMENTS = "tech_fr"
RES_GENIUS_FRAGMENTS = "gen_fr"
RES_BLOOD = "blood"  # капли крови
RES_DONATE = "donate"  # донат-коины (1 ₽ = 1), `users.donate_coins`

RESOURCES: tuple[str, ...] = (
    RES_COINS,
    RES_TICKETS,
    RES_DEV_POINTS,
    RES_PATH_POINTS,
    RES_PATH_FRAGMENTS,
    RES_TECHNIQUE_FRAGMENTS,
    RES_GENIUS_FRAGMENTS,
    RES_BLOOD,
    RES_DONATE,
)
# Ресурсы, которые нельзя «размножать» игровыми механиками: вклады с процентами и казино
# напечатали бы донат-валюту из воздуха. Биржа, ячейки и обменник клана — можно (перевод).
NO_MINT_RESOURCES: frozenset[str] = frozenset({RES_DONATE})

# Вид предмета: ресурс или отряд статистов (код — `StatistKey.encode()`), — для биржи.
ITEM_RESOURCE = "res"
ITEM_STATIST = "statist"
