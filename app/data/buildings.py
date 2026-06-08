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
    BuildingConfig("gym",        "Спортзал",        "🏋",  "legal",       5,   2, 0),
    BuildingConfig("cafe",       "Кафе",            "☕",  "legal",       5,   2, 0),
    BuildingConfig("shop",       "Магазин",         "🏪",  "legal",      15,   4, 0),
    BuildingConfig("hotel",      "Отель",           "🏨",  "legal",      40,   8, 0),
    BuildingConfig("mall",       "Торговый центр",  "🏬",  "legal",     100,  16, 0),

    # Нелегальные — Ур.0
    BuildingConfig("warehouse",  "Склад",           "📦",  "illegal",    6,   2, 0),
    BuildingConfig("lab",        "Лаборатория",     "🧪",  "illegal",   20,   4, 0),
    BuildingConfig("casino",     "Казино",          "🎰",  "illegal",   45,   8, 0),
    BuildingConfig("factory",    "Завод",           "🏭",  "illegal",   70,  12, 0),
    BuildingConfig("syndicate",  "Синдикат",        "🕶",  "illegal",  130,  16, 0),

    # Политические — Ур.0
    BuildingConfig("office",     "Офис",            "🏢",  "political",  4,   2, 0),
    BuildingConfig("media",      "СМИ",             "📡",  "political", 10,   4, 0),
    BuildingConfig("bank",       "Банк",            "🏦",  "political", 30,   8, 0),
    BuildingConfig("ministry",   "Министерство",    "🏛",  "political", 50,  12, 0),
    BuildingConfig("parliament", "Парламент",       "⚖️",  "political", 80,  16, 0),

    # ── Гений бизнеса Ур.1: Малый элитный бизнес ──────────────────────────────
    # 20 районов — вмещается в 32-районный город
    BuildingConfig("biz_center",  "Бизнес-центр",   "🗼",  "legal",    180,  20, 1),
    BuildingConfig("opg",         "ОПГ",            "🔫",  "illegal",  200,  20, 1),
    BuildingConfig("bureau",      "Ведомство",      "🏗",  "political", 160,  20, 1),

    # ── Гений бизнеса Ур.2: Средний элитный бизнес ────────────────────────────
    # 28 районов — вмещается в 32-районный город (4 свободных для манёвра)
    BuildingConfig("district_hq", "Деловой квартал","🌆",  "legal",    300,  28, 2),
    BuildingConfig("mafia",       "Мафия",          "☠️",  "illegal",  350,  28, 2),
    BuildingConfig("party_hq",    "Партийная машина","🌐", "political", 280,  28, 2),

    # ── Гений бизнеса Ур.3: Крупный элитный бизнес ────────────────────────────
    # 36 районов — нужен 64-районный город (половина большого)
    BuildingConfig("corporation", "Корпорация",     "💎",  "legal",    535,  36, 3),
    BuildingConfig("cartel",      "Картель",        "💀",  "illegal",  665,  36, 3),
    BuildingConfig("order",       "Орден",          "👁",  "political", 485,  36, 3),

    # ── Гений бизнеса Ур.4: Мегабизнес ───────────────────────────────────────
    # 48 районов — нужен 64-районный город (¾ большого)
    BuildingConfig("conglomerate","Конгломерат",    "🌍",  "legal",   1135,  48, 4),
    BuildingConfig("world_cartel","Мировой картель","🌑",  "illegal", 1335,  48, 4),
    BuildingConfig("world_order", "Мировой порядок","🔮", "political",1000,  48, 4),

    # ── Гений бизнеса Ур.5: Легендарный бизнес ────────────────────────────────
    # 64 районов — требует полного 64-районного города
    BuildingConfig("empire",      "Бизнес-империя", "👑",  "legal",   2165,  64, 5),
    BuildingConfig("shadow_throne","Теневой трон",  "♾️",  "illegal", 2500,  64, 5),
    BuildingConfig("shadow_gov",  "Теневое правительство","🌟","political",2000,64,5),

    # ══════════════════════════════════════════════════════════════════════════════
    # ЦИФРОВОЙ ПУТЬ — технологический бизнес
    # Особенность: при постройке каждого здания игрок получает card_dust
    # ══════════════════════════════════════════════════════════════════════════════

    # Цифровые — УНИКАЛЬНОСТЬ: тот же доход что у легального,
    # но ДЕШЕВЛЕ по районам (~25% скидка). Больше зданий в городе = выше суммарный доход.
    # Легальный для сравнения: 2/4/8/16 р. | Цифровой: 2/3/6/12 р.
    BuildingConfig("coworking",   "Коворкинг",             "💻",  "digital",   5,   2, 0),
    BuildingConfig("it_studio",   "IT-студия",              "🖥",  "digital",  15,   3, 0),
    BuildingConfig("startup",     "Стартап",                "📱",  "digital",  40,   6, 0),
    BuildingConfig("inet_co",     "Интернет-компания",      "🌐",  "digital",  55,   9, 0),
    BuildingConfig("techcorp",    "Технокорп",              "🤖",  "digital", 100,  12, 0),

    # ── Цифровой Ур.1  (лег. 180/20р → 180/16р)
    BuildingConfig("innov_hub",   "Инновационный хаб",     "🔬",  "digital",  180,  16, 1),

    # ── Цифровой Ур.2  (лег. 300/28р → 300/22р)
    BuildingConfig("silicon",     "Кремниевая долина",      "💡",  "digital",  300,  22, 2),

    # ── Цифровой Ур.3  (лег. 535/36р → 535/28р)
    BuildingConfig("tech_giant",  "Технологический гигант", "🛸",  "digital",  535,  28, 3),

    # ── Цифровой Ур.4  (лег. 1135/48р → 1135/38р)
    BuildingConfig("smart_city",  "Умный город",            "🌍",  "digital", 1135,  38, 4),

    # ── Цифровой Ур.5  (лег. 2165/64р → 2165/50р)
    BuildingConfig("digital_gov", "Цифровое государство",   "🏙",  "digital", 2165,  50, 5),
]

BUILDINGS_BY_ID: dict[str, BuildingConfig] = {b.id: b for b in BUILDINGS}
BUILDINGS_BY_PATH: dict[str, list[BuildingConfig]] = {}
for b in BUILDINGS:
    BUILDINGS_BY_PATH.setdefault(b.path, []).append(b)
