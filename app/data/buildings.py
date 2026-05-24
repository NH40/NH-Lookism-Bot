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
    BuildingConfig("gym",        "Спортзал",        "🏋",  "legal",     5,  2),
    BuildingConfig("cafe",       "Кафе",            "☕",  "legal",     5,  2),
    BuildingConfig("shop",       "Магазин",         "🏪",  "legal",     15,  4),
    BuildingConfig("hotel",      "Отель",           "🏨",  "legal",     40,  8),
    BuildingConfig("mall",       "Торговый центр",  "🏬",  "legal",    100, 16),

    # Нелегальные
    BuildingConfig("warehouse",  "Склад",           "📦",  "illegal",   6,  2),
    BuildingConfig("lab",        "Лаборатория",     "🧪",  "illegal",   20,  4),
    BuildingConfig("casino",     "Казино",          "🎰",  "illegal",   45,  8),
    BuildingConfig("factory",    "Завод",           "🏭",  "illegal",  70, 12),
    BuildingConfig("syndicate",  "Синдикат",        "🕶",  "illegal",  130, 16),
    # Политические
    BuildingConfig("office",     "Офис",            "🏢",  "political", 4,  2),
    BuildingConfig("media",      "СМИ",             "📡",  "political", 10,  4),
    BuildingConfig("bank",       "Банк",            "🏦",  "political", 30,  8),
    BuildingConfig("ministry",   "Министерство",    "🏛",  "political", 50, 12),
    BuildingConfig("parliament", "Парламент",       "⚖️",  "political", 80, 16),
]

BUILDINGS_BY_ID: dict[str, BuildingConfig] = {b.id: b for b in BUILDINGS}
BUILDINGS_BY_PATH: dict[str, list[BuildingConfig]] = {}
for b in BUILDINGS:
    BUILDINGS_BY_PATH.setdefault(b.path, []).append(b)