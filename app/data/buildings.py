from dataclasses import dataclass, field


@dataclass
class BuildingConfig:
    id: str
    name: str
    emoji: str
    path: str
    base_income: int
    district_cost: int      # кол-во районов для постройки
    min_biz_genius: int = 0 # минимальный уровень Гения бизнеса


# ── Базовые здания (Гений бизнеса Ур.0) ──────────────────────────────────────
BUILDINGS: list[BuildingConfig] = [
    # Легальные — Ур.0
    BuildingConfig("gym",        "Спортзал",        "🏋",  "legal",      12,   2, 0),
    BuildingConfig("cafe",       "Кафе",            "☕",  "legal",      12,   2, 0),
    BuildingConfig("shop",       "Магазин",         "🏪",  "legal",      33,   4, 0),
    BuildingConfig("hotel",      "Отель",           "🏨",  "legal",      90,   8, 0),
    BuildingConfig("mall",       "Торговый центр",  "🏬",  "legal",     225,  16, 0),

    # Нелегальные — Ур.0
    BuildingConfig("warehouse",  "Склад",           "📦",  "illegal",   14,   2, 0),
    BuildingConfig("lab",        "Лаборатория",     "🧪",  "illegal",   45,   4, 0),
    BuildingConfig("casino",     "Казино",          "🎰",  "illegal",  102,   8, 0),
    BuildingConfig("factory",    "Завод",           "🏭",  "illegal",  158,  12, 0),
    BuildingConfig("syndicate",  "Синдикат",        "🕶",  "illegal",  300,  16, 0),

    # Политические — Ур.0
    BuildingConfig("office",     "Офис",            "🏢",  "political",  9,   2, 0),
    BuildingConfig("media",      "СМИ",             "📡",  "political", 23,   4, 0),
    BuildingConfig("bank",       "Банк",            "🏦",  "political", 68,   8, 0),
    BuildingConfig("ministry",   "Министерство",    "🏛",  "political",113,  12, 0),
    BuildingConfig("parliament", "Парламент",       "⚖️",  "political",180,  16, 0),

    # ── Гений бизнеса Ур.1: Малый элитный бизнес ──────────────────────────────
    # 20 районов — вмещается в 32-районный город
    BuildingConfig("biz_center",  "Бизнес-центр",   "🗼",  "legal",    405,  20, 1),
    BuildingConfig("opg",         "ОПГ",            "🔫",  "illegal",  450,  20, 1),
    BuildingConfig("bureau",      "Ведомство",      "🏗",  "political", 360,  20, 1),

    # ── Гений бизнеса Ур.2: Средний элитный бизнес ────────────────────────────
    # 28 районов — вмещается в 32-районный город (4 свободных для манёвра)
    BuildingConfig("district_hq", "Деловой квартал","🌆",  "legal",    450,  28, 2),
    BuildingConfig("mafia",       "Мафия",          "☠️",  "illegal",  525,  28, 2),
    BuildingConfig("party_hq",    "Партийная машина","🌐", "political", 420,  28, 2),

    # ── Гений бизнеса Ур.3: Крупный элитный бизнес ────────────────────────────
    # 36 районов — нужен 64-районный город (половина большого)
    BuildingConfig("corporation", "Корпорация",     "💎",  "legal",    803,  36, 3),
    BuildingConfig("cartel",      "Картель",        "💀",  "illegal",  998,  36, 3),
    BuildingConfig("order",       "Орден",          "👁",  "political", 728,  36, 3),

    # ── Гений бизнеса Ур.4: Мегабизнес ───────────────────────────────────────
    # 48 районов — нужен 64-районный город (¾ большого)
    BuildingConfig("conglomerate","Конгломерат",    "🌍",  "legal",   1703,  48, 4),
    BuildingConfig("world_cartel","Мировой картель","🌑",  "illegal", 2003,  48, 4),
    BuildingConfig("world_order", "Мировой порядок","🔮", "political",1500,  48, 4),

    # ── Гений бизнеса Ур.5: Легендарный бизнес ────────────────────────────────
    # 64 районов — требует полного 64-районного города
    BuildingConfig("empire",      "Бизнес-империя", "👑",  "legal",   3248,  64, 5),
    BuildingConfig("shadow_throne","Теневой трон",  "♾️",  "illegal", 3750,  64, 5),
    BuildingConfig("shadow_gov",  "Теневое правительство","🌟","political",3000,64,5),

    # ══════════════════════════════════════════════════════════════════════════════
    # ЦИФРОВОЙ ПУТЬ — технологический бизнес
    # Особенность: при постройке каждого здания игрок получает card_dust
    # ══════════════════════════════════════════════════════════════════════════════

    # Цифровые — УНИКАЛЬНОСТЬ: тот же доход что у легального,
    # но ДЕШЕВЛЕ по районам (~25% скидка). Больше зданий в городе = выше суммарный доход.
    # Легальный для сравнения: 2/4/8/16 р. | Цифровой: 2/3/6/12 р.
    BuildingConfig("coworking",   "Коворкинг",             "💻",  "digital",   8,   2, 0),
    BuildingConfig("it_studio",   "IT-студия",              "🖥",  "digital",  23,   3, 0),
    BuildingConfig("startup",     "Стартап",                "📱",  "digital",  60,   6, 0),
    BuildingConfig("inet_co",     "Интернет-компания",      "🌐",  "digital",  83,   9, 0),
    BuildingConfig("techcorp",    "Технокорп",              "🤖",  "digital", 150,  12, 0),

    # ── Цифровой Ур.1  (лег. 405/20р → 405/16р)
    BuildingConfig("innov_hub",   "Инновационный хаб",     "🔬",  "digital",  270,  16, 1),

    # ── Цифровой Ур.2  (лег. 450/28р → 450/22р)
    BuildingConfig("silicon",     "Кремниевая долина",      "💡",  "digital",  450,  22, 2),

    # ── Цифровой Ур.3  (лег. 803/36р → 803/28р)
    BuildingConfig("tech_giant",  "Технологический гигант", "🛸",  "digital",  803,  28, 3),

    # ── Цифровой Ур.4  (лег. 1703/48р → 1703/38р)
    BuildingConfig("smart_city",  "Умный город",            "🌍",  "digital", 1703,  38, 4),

    # ── Цифровой Ур.5  (лег. 3248/64р → 3248/50р)
    BuildingConfig("digital_gov", "Цифровое государство",   "🏙",  "digital", 3248,  50, 5),
]

BUILDINGS_BY_ID: dict[str, BuildingConfig] = {b.id: b for b in BUILDINGS}
BUILDINGS_BY_PATH: dict[str, list[BuildingConfig]] = {}
for b in BUILDINGS:
    BUILDINGS_BY_PATH.setdefault(b.path, []).append(b)
