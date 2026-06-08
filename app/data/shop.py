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


# Статисты: цены ÷2 от старых (армия строится вдвое медленнее — создаёт сопротивление)
SHOP_ITEMS: list[ShopItem] = [
    ShopItem("recruit_f",   "⬛ Статист F",   "Боец F-ранга | 5 за шт.",              5,         "recruit"),
    ShopItem("recruit_e",   "⬜ Статист E",   "Боец E-ранга | 50 за шт.",            50,         "recruit"),
    ShopItem("recruit_d",   "🟦 Статист D",   "Боец D-ранга | 100 за шт.",          100,       "recruit"),
    ShopItem("recruit_c",   "🟩 Статист C",   "Боец C-ранга | 250 за шт.",          250,       "recruit"),
    ShopItem("recruit_b",   "🟨 Статист B",   "Боец B-ранга | 500 за шт.",          500,      "recruit"),
    ShopItem("recruit_a",   "🟧 Статист A",   "Боец A-ранга | 750 за шт.",          750,      "recruit"),
    ShopItem("recruit_s",   "🟥 Статист S",   "Боец S-ранга | 1,000 за шт.",      1_000,      "recruit"),
    ShopItem("recruit_ss",  "💠 Статист SS",  "Боец SS-ранга | 1,200 за шт.",     1_200,     "recruit"),
    ShopItem("recruit_sss", "🔷 Статист SSS", "Боец SSS-ранга | 1,500 за шт.",    1_500,     "recruit"),
    ShopItem("recruit_sr",  "🌟 Статист SR",  "Боец SR-ранга | 2,250 за шт.",     2_250,     "recruit"),
    ShopItem("recruit_ssr", "✨ Статист SSR", "Боец SSR-ранга | 2,500 за шт.",    2_500,   "recruit"),
    ShopItem("recruit_ur",  "💎 Статист UR",  "Боец UR-ранга | 3,000 за шт.",     3_000,   "recruit"),
    ShopItem("recruit_lr",  "👑 Статист LR",  "Боец LR-ранга | 5,000 за шт.",     5_000,  "recruit"),
    ShopItem("recruit_mp",  "🔱 Статист MP",  "Боец MP-ранга | 6,000 за шт.",     6_000,  "recruit"),
    ShopItem("recruit_x",   "⚡ Статист X",   "Боец X-ранга | 7,500 за шт.",      7_500, "recruit"),
    ShopItem("recruit_xx",  "🌀 Статист XX",  "Боец XX-ранга | 12,500 за шт.",   12_500, "recruit"),
    ShopItem("recruit_xxx", "🔥 Статист XXX", "Боец XXX-ранга | 20,000 за шт.", 20_000, "recruit"),
    ShopItem("recruit_dx",  "💀 Статист DX",  "Боец DX-ранга | 25,000 за шт.", 25_000, "recruit"),
]

# ── Тировые зелья Гения медицины — 6 тиров по каждому типу ──────────────────
# Цены ÷3: зелья — ежедневный расходник, должен быть доступен.
# Эффекты: максимум 120% (вместо 150-200%).

MG_TIERS: dict[str, list[PotionConfig]] = {
    # Зелье силы:       Ур.6 = +120% мощь
    # Зелье тренировки: Ур.6 = +120%
    # Зелье богатства:  Ур.6 = +120% доход
    # Зелье удачи:      Ур.6 = +25% шанс тикета
    # Зелье влияния:    Ур.6 = +120%
    # Зелье охотника:   Ур.6 = +75% дроп

    "power": [
        PotionConfig("mg_power_1", "⚔️ Зелье силы I",        "Мощь +20%, 30 мин",           "power",     20, 30,     5_700),
        PotionConfig("mg_power_2", "⚔️ Зелье силы II",       "Мощь +40%, 30 мин",           "power",     40, 30,    17_000),
        PotionConfig("mg_power_3", "⚔️ Зелье силы III",      "Мощь +60%, 30 мин",           "power",     60, 30,    60_000),
        PotionConfig("mg_power_4", "⚔️ Зелье силы IV",       "Мощь +80%, 30 мин",           "power",     80, 30,   180_000),
        PotionConfig("mg_power_5", "⚔️ Зелье силы V",        "Мощь +100%, 30 мин",          "power",    100, 30,   585_000),
        PotionConfig("mg_power_6", "⚔️ Зелье силы VI",       "Мощь +120%, 30 мин",          "power",    120, 30, 1_835_000),
    ],
    "training": [
        PotionConfig("mg_train_1", "🏋 Зелье тренировки I",  "Тренировка +20%, 60 мин",     "training",  20, 60,     4_000),
        PotionConfig("mg_train_2", "🏋 Зелье тренировки II", "Тренировка +35%, 60 мин",     "training",  35, 60,    13_000),
        PotionConfig("mg_train_3", "🏋 Зелье тренировки III","Тренировка +55%, 60 мин",     "training",  55, 60,    45_000),
        PotionConfig("mg_train_4", "🏋 Зелье тренировки IV", "Тренировка +75%, 60 мин",     "training",  75, 60,   135_000),
        PotionConfig("mg_train_5", "🏋 Зелье тренировки V",  "Тренировка +95%, 60 мин",     "training",  95, 60,   440_000),
        PotionConfig("mg_train_6", "🏋 Зелье тренировки VI", "Тренировка +120%, 60 мин",    "training", 120, 60, 1_335_000),
    ],
    "income": [
        PotionConfig("mg_income_1", "💰 Зелье богатства I",  "Доход +20%, 60 мин",          "income",    20, 60,     5_500),
        PotionConfig("mg_income_2", "💰 Зелье богатства II", "Доход +40%, 60 мин",          "income",    40, 60,    17_000),
        PotionConfig("mg_income_3", "💰 Зелье богатства III","Доход +65%, 60 мин",          "income",    65, 60,    60_000),
        PotionConfig("mg_income_4", "💰 Зелье богатства IV", "Доход +85%, 60 мин",          "income",    85, 60,   180_000),
        PotionConfig("mg_income_5", "💰 Зелье богатства V",  "Доход +100%, 60 мин",         "income",   100, 60,   585_000),
        PotionConfig("mg_income_6", "💰 Зелье богатства VI", "Доход +120%, 60 мин",         "income",   120, 60, 1_835_000),
    ],
    "luck": [
        PotionConfig("mg_luck_1", "🍀 Зелье удачи I",        "Шанс тикета +5%, 30 мин",     "luck",       5, 30,     3_500),
        PotionConfig("mg_luck_2", "🍀 Зелье удачи II",       "Шанс тикета +9%, 30 мин",     "luck",       9, 30,    10_000),
        PotionConfig("mg_luck_3", "🍀 Зелье удачи III",      "Шанс тикета +13%, 30 мин",    "luck",      13, 30,    37_000),
        PotionConfig("mg_luck_4", "🍀 Зелье удачи IV",       "Шанс тикета +17%, 30 мин",    "luck",      17, 30,   110_000),
        PotionConfig("mg_luck_5", "🍀 Зелье удачи V",        "Шанс тикета +21%, 30 мин",    "luck",      21, 30,   365_000),
        PotionConfig("mg_luck_6", "🍀 Зелье удачи VI",       "Шанс тикета +25%, 30 мин",    "luck",      25, 30, 1_100_000),
    ],
    "influence": [
        PotionConfig("mg_infl_1", "⚡ Зелье влияния I",      "Влияние +20%, 45 мин",        "influence", 20, 45,     5_000),
        PotionConfig("mg_infl_2", "⚡ Зелье влияния II",     "Влияние +40%, 45 мин",        "influence", 40, 45,    15_000),
        PotionConfig("mg_infl_3", "⚡ Зелье влияния III",    "Влияние +65%, 45 мин",        "influence", 65, 45,    53_000),
        PotionConfig("mg_infl_4", "⚡ Зелье влияния IV",     "Влияние +90%, 45 мин",        "influence", 90, 45,   160_000),
        PotionConfig("mg_infl_5", "⚡ Зелье влияния V",      "Влияние +105%, 45 мин",       "influence",105, 45,   535_000),
        PotionConfig("mg_infl_6", "⚡ Зелье влияния VI",     "Влияние +120%, 45 мин",       "influence",120, 45, 1_600_000),
    ],
    "raid_drop": [
        PotionConfig("mg_raid_1", "💠 Зелье охотника I",     "Дроп +15%, 60 мин",           "raid_drop", 15, 60,    11_500),
        PotionConfig("mg_raid_2", "💠 Зелье охотника II",    "Дроп +25%, 60 мин",           "raid_drop", 25, 60,    33_500),
        PotionConfig("mg_raid_3", "💠 Зелье охотника III",   "Дроп +38%, 60 мин",           "raid_drop", 38, 60,   120_000),
        PotionConfig("mg_raid_4", "💠 Зелье охотника IV",    "Дроп +50%, 60 мин",           "raid_drop", 50, 60,   360_000),
        PotionConfig("mg_raid_5", "💠 Зелье охотника V",     "Дроп +62%, 60 мин",           "raid_drop", 62, 60, 1_185_000),
        PotionConfig("mg_raid_6", "💠 Зелье охотника VI",    "Дроп +75%, 60 мин",           "raid_drop", 75, 60, 3_565_000),
    ],
}

# Плоский словарь для быстрого поиска по potion_id
MG_TIER_MAP: dict[str, PotionConfig] = {
    p.potion_id: p
    for tiers in MG_TIERS.values()
    for p in tiers
}

MG_POWER_TIERS = MG_TIERS["power"]
MG_POWER_MAP   = {p.potion_id: p for p in MG_POWER_TIERS}

POTIONS: list[PotionConfig] = []
POTION_MAP: dict[str, PotionConfig] = {}
SHOP_MAP:   dict[str, ShopItem]     = {i.item_id: i for i in SHOP_ITEMS}

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
