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
    ShopItem("recruit_f",   "⬛ Статист F",   "Боец F-ранга | 100 за шт.",            100,         "recruit"),
    ShopItem("recruit_e",   "⬜ Статист E",   "Боец E-ранга | 750 за шт.",            750,         "recruit"),
    ShopItem("recruit_d",   "🟦 Статист D",   "Боец D-ранга | 2,500 за шт.",          2_500,       "recruit"),
    ShopItem("recruit_c",   "🟩 Статист C",   "Боец C-ранга | 5,000 за шт.",          5_000,       "recruit"),
    ShopItem("recruit_b",   "🟨 Статист B",   "Боец B-ранга | 25,000 за шт.",         25_000,      "recruit"),
    ShopItem("recruit_a",   "🟧 Статист A",   "Боец A-ранга | 50,000 за шт.",         50_000,      "recruit"),
    ShopItem("recruit_s",   "🟥 Статист S",   "Боец S-ранга | 60,000 за шт.",         60_000,      "recruit"),
    ShopItem("recruit_ss",  "💠 Статист SS",  "Боец SS-ранга | 150,000 за шт.",       150_000,     "recruit"),
    ShopItem("recruit_sss", "🔷 Статист SSS", "Боец SSS-ранга | 300,000 за шт.",      300_000,     "recruit"),
    ShopItem("recruit_sr",  "🌟 Статист SR",  "Боец SR-ранга | 700,000 за шт.",       700_000,     "recruit"),
    ShopItem("recruit_ssr", "✨ Статист SSR", "Боец SSR-ранга | 2,000,000 за шт.",    2_000_000,   "recruit"),
    ShopItem("recruit_ur",  "💎 Статист UR",  "Боец UR-ранга | 5,000,000 за шт.",     5_000_000,   "recruit"),
    ShopItem("recruit_lr",  "👑 Статист LR",  "Боец LR-ранга | 15,000,000 за шт.",    15_000_000,  "recruit"),
    ShopItem("recruit_mp",  "🔱 Статист MP",  "Боец MP-ранга | 40,000,000 за шт.",    40_000_000,  "recruit"),
    ShopItem("recruit_x",   "⚡ Статист X",   "Боец X-ранга | 100,000,000 за шт.",    100_000_000, "recruit"),
    ShopItem("recruit_xx",  "🌀 Статист XX",  "Боец XX-ранга | 250,000,000 за шт.",   250_000_000, "recruit"),
    ShopItem("recruit_xxx", "🔥 Статист XXX", "Боец XXX-ранга | 600,000,000 за шт.",  600_000_000, "recruit"),
    ShopItem("recruit_dx",  "💀 Статист DX",  "Боец DX-ранга | 1,500,000,000 за шт.", 1_500_000_000, "recruit"),
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
    "DX":    "recruit_dx",
}