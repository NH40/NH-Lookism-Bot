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

POTIONS: list[PotionConfig] = [
    PotionConfig("potion_combat",    "⚔️ Зелье силы",       "Боевая мощь +30% на 30 минут",      "combat_power", 30, 30, 25_000),
    PotionConfig("potion_income",    "💰 Зелье богатства",  "Доход +50% на 60 минут",             "income",       50, 60, 20_000),
    PotionConfig("potion_influence", "⚡ Зелье влияния",    "Влияние +40% на 45 минут",           "influence",    40, 45, 18_000),
    PotionConfig("potion_training",  "🏋 Зелье тренировки", "Охват тренировки +25% на 60 минут",  "training",     25, 60, 15_000),
    PotionConfig("potion_luck",      "🍀 Зелье удачи",      "Шанс тикета +20% на 30 минут",       "luck",         20, 30, 12_000),
]

POTION_MAP: dict[str, PotionConfig] = {p.potion_id: p for p in POTIONS}
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