from dataclasses import dataclass


@dataclass
class BuildingConfig:
    id: str
    name: str
    emoji: str
    path: str
    base_income: int
    district_cost: int  # кратно 2, мин 1, макс 16


BUILDINGS: list[BuildingConfig] = [
    # Легальные
    BuildingConfig("gym",        "Спортзал",        "🏋",  "legal",     15,  2),
    BuildingConfig("cafe",       "Кафе",            "☕",  "legal",     25,  2),
    BuildingConfig("shop",       "Магазин",         "🏪",  "legal",     40,  4),
    BuildingConfig("hotel",      "Отель",           "🏨",  "legal",     80,  8),
    BuildingConfig("mall",       "Торговый центр",  "🏬",  "legal",    150, 16),
    # Нелегальные
    BuildingConfig("warehouse",  "Склад",           "📦",  "illegal",   20,  2),
    BuildingConfig("lab",        "Лаборатория",     "🧪",  "illegal",   45,  4),
    BuildingConfig("casino",     "Казино",          "🎰",  "illegal",   90,  8),
    BuildingConfig("factory",    "Завод",           "🏭",  "illegal",  170, 12),
    BuildingConfig("syndicate",  "Синдикат",        "🕶",  "illegal",  300, 16),
    # Политические
    BuildingConfig("office",     "Офис",            "🏢",  "political", 18,  2),
    BuildingConfig("media",      "СМИ",             "📡",  "political", 35,  4),
    BuildingConfig("bank",       "Банк",            "🏦",  "political", 70,  8),
    BuildingConfig("ministry",   "Министерство",    "🏛",  "political", 130, 12),
    BuildingConfig("parliament", "Парламент",       "⚖️",  "political", 250, 16),
]

BUILDINGS_BY_ID: dict[str, BuildingConfig] = {b.id: b for b in BUILDINGS}
BUILDINGS_BY_PATH: dict[str, list[BuildingConfig]] = {}
for b in BUILDINGS:
    BUILDINGS_BY_PATH.setdefault(b.path, []).append(b)