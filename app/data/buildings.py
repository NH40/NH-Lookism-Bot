from dataclasses import dataclass

@dataclass
class BuildingConfig:
    id: str
    name: str
    emoji: str
    path: str          # "legal" | "illegal" | "political"
    base_income: int   # NHCoin/мин за 1 здание
    district_cost: int # стоит N районов игрока

BUILDINGS: list[BuildingConfig] = [
    # Легальные
    BuildingConfig("gym",        "Спортзал",          "🏋",  "legal",     15,  2),
    BuildingConfig("cafe",       "Кафе",              "☕",  "legal",     25,  3),
    BuildingConfig("shop",       "Магазин",           "🏪",  "legal",     40,  5),
    BuildingConfig("hotel",      "Отель",             "🏨",  "legal",     80,  8),
    BuildingConfig("mall",       "Торговый центр",    "🏬",  "legal",    150, 15),
    # Нелегальные
    BuildingConfig("warehouse",  "Склад",             "📦",  "illegal",   20,  2),
    BuildingConfig("lab",        "Лаборатория",       "🧪",  "illegal",   45,  5),
    BuildingConfig("casino",     "Казино",            "🎰",  "illegal",   90,  9),
    BuildingConfig("factory",    "Завод",             "🏭",  "illegal",  170, 16),
    BuildingConfig("syndicate",  "Синдикат",          "🕶",  "illegal",  300, 25),
    # Политические
    BuildingConfig("office",     "Офис",              "🏢",  "political", 18,  2),
    BuildingConfig("media",      "СМИ",               "📡",  "political", 35,  4),
    BuildingConfig("bank",       "Банк",              "🏦",  "political", 70,  7),
    BuildingConfig("ministry",   "Министерство",      "🏛",  "political", 130, 13),
    BuildingConfig("parliament", "Парламент",         "⚖️",  "political", 250, 22),
]

BUILDINGS_BY_ID: dict[str, BuildingConfig] = {b.id: b for b in BUILDINGS}
BUILDINGS_BY_PATH: dict[str, list[BuildingConfig]] = {}
for b in BUILDINGS:
    BUILDINGS_BY_PATH.setdefault(b.path, []).append(b)