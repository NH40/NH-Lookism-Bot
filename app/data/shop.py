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
    # Статисты — цена за 1 шт, количество выбирается отдельно
    ShopItem("recruit_e", "⚪ Статист E", "Боец E-ранга | 750 за шт.",    750,   "recruit"),
    ShopItem("recruit_d", "🟢 Статист D", "Боец D-ранга | 2,500 за шт.",    2_500,   "recruit"),
    ShopItem("recruit_c", "🔵 Статист C", "Боец C-ранга | 5,000 за шт.",    5_000,   "recruit"),
    ShopItem("recruit_b", "🟣 Статист B", "Боец B-ранга | 25,000 за шт.",   25_000,  "recruit"),
    ShopItem("recruit_a", "🟡 Статист A", "Боец A-ранга | 50,000 за шт.",   50_000,  "recruit"),
    ShopItem("recruit_s", "🔴 Статист S", "Боец S-ранга | 60,000 за шт.",  60_000, "recruit"),
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
    "E": "recruit_e",
    "D": "recruit_d",
    "C": "recruit_c",
    "B": "recruit_b",
    "A": "recruit_a",
    "S": "recruit_s",
}