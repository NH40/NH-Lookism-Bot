from dataclasses import dataclass


@dataclass(frozen=True)
class ShopItem:
    item_id: str
    name: str
    description: str
    price: int
    category: str


@dataclass(frozen=True)
class PotionConfig:
    potion_id: str
    name: str
    description: str
    effect_key: str
    effect_value: int
    duration_minutes: int
    price: int


SHOP_ITEMS: list[ShopItem] = [
    ShopItem("recruit_f",   "⬛ Статист F",   "Боец F-ранга | 10 за шт.",            10,         "recruit"),
    ShopItem("recruit_e",   "⬜ Статист E",   "Боец E-ранга | 50 за шт.",            100,         "recruit"),
    ShopItem("recruit_d",   "🟦 Статист D",   "Боец D-ранга | 200 за шт.",          200,       "recruit"),
    ShopItem("recruit_c",   "🟩 Статист C",   "Боец C-ранга | 500 за шт.",          500,       "recruit"),
    ShopItem("recruit_b",   "🟨 Статист B",   "Боец B-ранга | 1,000 за шт.",         1_000,      "recruit"),
    ShopItem("recruit_a",   "🟧 Статист A",   "Боец A-ранга | 1,500 за шт.",         1_500,      "recruit"),
    ShopItem("recruit_s",   "🟥 Статист S",   "Боец S-ранга | 2,000 за шт.",         2_000,      "recruit"),
    ShopItem("recruit_ss",  "💠 Статист SS",  "Боец SS-ранга | 2,400 за шт.",       2_400,     "recruit"),
    ShopItem("recruit_sss", "🔷 Статист SSS", "Боец SSS-ранга | 3,000 за шт.",      3_000,     "recruit"),
    ShopItem("recruit_sr",  "🌟 Статист SR",  "Боец SR-ранга | 4,500 за шт.",       4_500,     "recruit"),
    ShopItem("recruit_ssr", "✨ Статист SSR", "Боец SSR-ранга | 5,000 за шт.",    5_000,   "recruit"),
    ShopItem("recruit_ur",  "💎 Статист UR",  "Боец UR-ранга | 6,000 за шт.",     6_000,   "recruit"),
    ShopItem("recruit_lr",  "👑 Статист LR",  "Боец LR-ранга | 10,000 за шт.",    10_000,  "recruit"),
    ShopItem("recruit_mp",  "🔱 Статист MP",  "Боец MP-ранга | 12,000 за шт.",    12_000,  "recruit"),
    ShopItem("recruit_x",   "⚡ Статист X",   "Боец X-ранга | 15,000 за шт.",    15_000, "recruit"),
    ShopItem("recruit_xx",  "🌀 Статист XX",  "Боец XX-ранга | 25,000 за шт.",   25_000, "recruit"),
    ShopItem("recruit_xxx", "🔥 Статист XXX", "Боец XXX-ранга | 40,000 за шт.",  40_000, "recruit"),
    ShopItem("recruit_dx",  "💀 Статист DX",  "Боец DX-ранга | 50,500 за шт.", 50_000, "recruit"),
]

# ── Тировые зелья Гения медицины — 6 тиров по каждому типу ──────────────────
# Индекс = mg_level - 1 (0-based). Тир 6 — только донат (ui_potion).

MG_TIERS: dict[str, list[PotionConfig]] = {
    # Цены растут ~×3 за каждый тир. Эффекты: равномерная прогрессия к максимуму.
    #
    # Зелье силы:      Ур.6 = +150% мощь
    # Зелье тренировки: Ур.6 = +130%
    # Зелье богатства:  Ур.6 = +200% доход
    # Зелье удачи:      Ур.6 = +25% шанс тикета
    # Зелье влияния:    Ур.6 = +200%
    # Зелье охотника:   Ур.6 = +75% дроп

    "power": [
        PotionConfig("mg_power_1", "⚔️ Зелье силы I",        "Мощь +30%, 30 мин",           "power",     30, 30,    20_000),
        PotionConfig("mg_power_2", "⚔️ Зелье силы II",       "Мощь +50%, 30 мин",           "power",     50, 30,    60_000),
        PotionConfig("mg_power_3", "⚔️ Зелье силы III",      "Мощь +75%, 30 мин",           "power",     75, 30,   180_000),
        PotionConfig("mg_power_4", "⚔️ Зелье силы IV",       "Мощь +100%, 30 мин",          "power",    100, 30,   540_000),
        PotionConfig("mg_power_5", "⚔️ Зелье силы V",        "Мощь +125%, 30 мин",          "power",    125, 30, 1_600_000),
        PotionConfig("mg_power_6", "⚔️ Зелье силы VI",       "Мощь +150%, 30 мин",          "power",    150, 30, 5_000_000),
    ],
    "training": [
        PotionConfig("mg_train_1", "🏋 Зелье тренировки I",  "Тренировка +25%, 60 мин",     "training",  25, 60,    15_000),
        PotionConfig("mg_train_2", "🏋 Зелье тренировки II", "Тренировка +38%, 60 мин",     "training",  38, 60,    45_000),
        PotionConfig("mg_train_3", "🏋 Зелье тренировки III","Тренировка +55%, 60 мин",     "training",  55, 60,   135_000),
        PotionConfig("mg_train_4", "🏋 Зелье тренировки IV", "Тренировка +75%, 60 мин",     "training",  75, 60,   400_000),
        PotionConfig("mg_train_5", "🏋 Зелье тренировки V",  "Тренировка +100%, 60 мин",    "training", 100, 60, 1_200_000),
        PotionConfig("mg_train_6", "🏋 Зелье тренировки VI", "Тренировка +130%, 60 мин",    "training", 130, 60, 3_600_000),
    ],
    "income": [
        PotionConfig("mg_income_1", "💰 Зелье богатства I",  "Доход +40%, 60 мин",          "income",    40, 60,    20_000),
        PotionConfig("mg_income_2", "💰 Зелье богатства II", "Доход +70%, 60 мин",          "income",    70, 60,    60_000),
        PotionConfig("mg_income_3", "💰 Зелье богатства III","Доход +105%, 60 мин",         "income",   105, 60,   180_000),
        PotionConfig("mg_income_4", "💰 Зелье богатства IV", "Доход +140%, 60 мин",         "income",   140, 60,   540_000),
        PotionConfig("mg_income_5", "💰 Зелье богатства V",  "Доход +170%, 60 мин",         "income",   170, 60, 1_600_000),
        PotionConfig("mg_income_6", "💰 Зелье богатства VI", "Доход +200%, 60 мин",         "income",   200, 60, 5_000_000),
    ],
    "luck": [
        PotionConfig("mg_luck_1", "🍀 Зелье удачи I",        "Шанс тикета +5%, 30 мин",     "luck",       5, 30,    12_000),
        PotionConfig("mg_luck_2", "🍀 Зелье удачи II",       "Шанс тикета +9%, 30 мин",     "luck",       9, 30,    36_000),
        PotionConfig("mg_luck_3", "🍀 Зелье удачи III",      "Шанс тикета +13%, 30 мин",    "luck",      13, 30,   110_000),
        PotionConfig("mg_luck_4", "🍀 Зелье удачи IV",       "Шанс тикета +17%, 30 мин",    "luck",      17, 30,   330_000),
        PotionConfig("mg_luck_5", "🍀 Зелье удачи V",        "Шанс тикета +21%, 30 мин",    "luck",      21, 30,   990_000),
        PotionConfig("mg_luck_6", "🍀 Зелье удачи VI",       "Шанс тикета +25%, 30 мин",    "luck",      25, 30, 3_000_000),
    ],
    "influence": [
        PotionConfig("mg_infl_1", "⚡ Зелье влияния I",      "Влияние +40%, 45 мин",        "influence", 40, 45,    18_000),
        PotionConfig("mg_infl_2", "⚡ Зелье влияния II",     "Влияние +60%, 45 мин",        "influence", 60, 45,    54_000),
        PotionConfig("mg_infl_3", "⚡ Зелье влияния III",    "Влияние +85%, 45 мин",        "influence", 85, 45,   160_000),
        PotionConfig("mg_infl_4", "⚡ Зелье влияния IV",     "Влияние +115%, 45 мин",       "influence",115, 45,   480_000),
        PotionConfig("mg_infl_5", "⚡ Зелье влияния V",      "Влияние +150%, 45 мин",       "influence",150, 45, 1_450_000),
        PotionConfig("mg_infl_6", "⚡ Зелье влияния VI",     "Влияние +200%, 45 мин",       "influence",200, 45, 4_350_000),
    ],
    "raid_drop": [
        PotionConfig("mg_raid_1", "💠 Зелье охотника I",     "Дроп +15%, 60 мин",           "raid_drop", 15, 60,    40_000),
        PotionConfig("mg_raid_2", "💠 Зелье охотника II",    "Дроп +25%, 60 мин",           "raid_drop", 25, 60,   120_000),
        PotionConfig("mg_raid_3", "💠 Зелье охотника III",   "Дроп +38%, 60 мин",           "raid_drop", 38, 60,   360_000),
        PotionConfig("mg_raid_4", "💠 Зелье охотника IV",    "Дроп +50%, 60 мин",           "raid_drop", 50, 60, 1_080_000),
        PotionConfig("mg_raid_5", "💠 Зелье охотника V",     "Дроп +62%, 60 мин",           "raid_drop", 62, 60, 3_240_000),
        PotionConfig("mg_raid_6", "💠 Зелье охотника VI",    "Дроп +75%, 60 мин",           "raid_drop", 75, 60, 9_700_000),
    ],
}

# Плоский словарь для быстрого поиска по potion_id
MG_TIER_MAP: dict[str, PotionConfig] = {
    p.potion_id: p
    for tiers in MG_TIERS.values()
    for p in tiers
}

# Первый тир каждого типа (обратная совместимость с кланами/clan POTION_CONFIG)
# Устаревшие flat-списки сохраняем для clan shop и других мест
MG_POWER_TIERS = MG_TIERS["power"]
MG_POWER_MAP   = {p.potion_id: p for p in MG_POWER_TIERS}

# ── Устаревший список плоских зелий (без тиров) — только для кланового магазина ─
POTIONS: list[PotionConfig] = []   # больше не используется в основном магазине
POTION_MAP: dict[str, PotionConfig] = {}
SHOP_MAP:   dict[str, ShopItem]     = {i.item_id:   i for i in SHOP_ITEMS}

CATEGORY_LABELS: dict[str, str] = {
    "recruit": "👥 Статисты",
    "potions": "🧪 Зелья",
}

RECRUIT_RANK_TO_ITEM: dict[str, str] = {
    "F":     "recruit_f",
    "E":     "recruit_e",
    "D":     "recruit_d",
    "C":     "recruit_c",
    "B":     "recruit_b",
    "A":     "recruit_a",
    "S":     "recruit_s",
    "SS":    "recruit_ss",
    "SSS":   "recruit_sss",
    "SR":    "recruit_sr",
    "SSR":   "recruit_ssr",
    "UR":    "recruit_ur",
    "LR":    "recruit_lr",
    "MP":    "recruit_mp",
    "X":     "recruit_x",
    "XX":    "recruit_xx",
    "XXX":   "recruit_xxx",
    "DX":    "recruit_dx"
}