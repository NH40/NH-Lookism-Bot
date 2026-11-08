"""Журналы (константы): причины изменений, виды имущества, виды боёв и записей журнала ошибок."""
from __future__ import annotations

# Причины, которые сервис задаёт явно. Остальное описывает источник: кнопка, команда, запрос Mini App.
REASON_INCOME = "income"  # доход зданий (строки за час сливаются в одну)
REASON_EMPEROR_TAX = "emperor_tax"  # налог и пассивный бонус императору (тоже сливаются)
REASON_MANAGER_BURN = "manager_burn"  # абсолют «Менеджер» сжёг монеты напавшего
REASON_ELITE_LOOT = "elite_loot"  # родословная Элиты: победитель забрал монеты проигравшего
REASON_SABOTAGE = "sabotage"  # кража из казны императора
REASON_WAR_TREASURY = "war_treasury"  # казна проигравшего в войне императоров или бою за трон

# Коды `player_ledger.asset` — их пишут триггеры (миграция a1d5e8c2f7b3).
ASSET_NH = "nh"
ASSET_DONATE = "donate"
ASSET_TICKETS = "tickets"
ASSET_STATISTS = "statists"
ASSET_CARD = "card"
ASSET_DISTRICT = "district"
ASSET_BUILDING = "building"
ASSET_PROFILE = "profile"
ASSETS_MONEY: tuple[str, ...] = (ASSET_NH, ASSET_DONATE)
ASSETS_GOODS: tuple[str, ...] = (
    ASSET_TICKETS, ASSET_STATISTS, ASSET_CARD, ASSET_DISTRICT, ASSET_BUILDING, "dev_points", "potential_points", "path_points",
    "path_fragments", "technique_fragments", "genius_fragments", "blood_drops", "skip_scrolls",
)

BATTLE_BOTS = "bots"
BATTLE_CITY = "city"
BATTLE_PVP = "pvp"
BATTLE_BOSS = "boss"
BATTLE_TOM = "tom"
BATTLE_THRONE = "throne"
BATTLE_WAR = "war"
DETAILED_BATTLES: frozenset[str] = frozenset({BATTLE_PVP, BATTLE_THRONE, BATTLE_WAR})

LOG_KIND_ERROR = "error"
LOG_KIND_SLOW = "slow"
