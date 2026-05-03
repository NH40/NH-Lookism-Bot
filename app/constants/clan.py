from dataclasses import dataclass


@dataclass(frozen=True)
class ClanShopItem:
    item_id: str
    name: str
    desc: str
    price: int
    category: str
    item_type: str
    value: object


# ── Категории ──────────────────────────────────────────────────────────────────
CLAN_SHOP_CATEGORIES = {
    "tickets":   "🎟 Тикеты",
    "potions":   "🧪 Зелья",
    "squad":     "👥 Статисты",
    "character": "🎴 Персонажи",
    "auction":   "🏛 Аукцион",
}

CLAN_SHOP_ITEMS: list[ClanShopItem] = [

    # ── Тикеты ────────────────────────────────────────────────────────────────
    ClanShopItem("tickets_1_all",  "🎟 1 тикет всем",   "Выдать 1 тикет всем",   3_750_000,   "tickets", "tickets", 1),
    ClanShopItem("tickets_3_all",  "🎟 3 тикета всем",  "Выдать 3 тикета всем",  10_000_000,   "tickets", "tickets", 3),
    ClanShopItem("tickets_5_all",  "🎟 5 тикетов всем", "Выдать 5 тикетов всем", 15_000_000,   "tickets", "tickets", 5),
    ClanShopItem("tickets_10_all", "🎟 10 тикетов всем","Выдать 10 тикетов всем",25_000_000, "tickets", "tickets", 10),

    # ── Зелья ─────────────────────────────────────────────────────────────────
    ClanShopItem("potion_combat_all",    "⚔️ Зелье силы всем",       "Боевая мощь +30% на 30 мин всем",     1_000_000, "potions", "potion", "potion_combat"),
    ClanShopItem("potion_income_all",    "💰 Зелье богатства всем",  "Доход +50% на 60 мин всем",           800_000,   "potions", "potion", "potion_income"),
    ClanShopItem("potion_influence_all", "⚡ Зелье влияния всем",    "Влияние +40% на 45 мин всем",         700_000,   "potions", "potion", "potion_influence"),
    ClanShopItem("potion_training_all",  "🏋 Зелье тренировки всем", "Охват тренировки +25% на 60 мин всем",600_000,  "potions", "potion", "potion_training"),
    ClanShopItem("potion_luck_all",      "🍀 Зелье удачи всем",      "Шанс тикета +20% на 30 мин всем",     500_000,   "potions", "potion", "potion_luck"),

    # ── Статисты ──────────────────────────────────────────────────────────────
    ClanShopItem("squad_s_all",   "🟥 100×S всем",   "100 статистов S всем",   1_000_000,  "squad", "squad", {"rank": "S",   "amount": 100}),
    ClanShopItem("squad_ss_all",  "💠 50×SS всем",   "50 статистов SS всем",   2_500_000,  "squad", "squad", {"rank": "SS",  "amount": 50}),
    ClanShopItem("squad_sss_all", "🔷 30×SSS всем",  "30 статистов SSS всем",  3_000_000, "squad", "squad", {"rank": "SSS", "amount": 30}),
    ClanShopItem("squad_sr_all",  "🌟 20×SR всем",   "20 статистов SR всем",   4_000_000, "squad", "squad", {"rank": "SR",  "amount": 20}),
    ClanShopItem("squad_ssr_all", "✨ 10×SSR всем",  "10 статистов SSR всем", 5_000_000, "squad", "squad", {"rank": "SSR", "amount": 10}),
    ClanShopItem("squad_ur_all",  "💎 5×UR всем",    "5 статистов UR всем",   8_000_000, "squad", "squad", {"rank": "UR",  "amount": 5}),

    # ── Персонажи ─────────────────────────────────────────────────────────────
    ClanShopItem("char_member_all",    "⬜ Персонаж member всем",    "Случайный member всем",    2_000_000,   "character", "character", "member"),
    ClanShopItem("char_boss_all",      "🟦 Персонаж boss всем",      "Случайный boss всем",      4_000_000,   "character", "character", "boss"),
    ClanShopItem("char_king_all",      "🟩 Персонаж king всем",      "Случайный king всем",      8_000_000,   "character", "character", "king"),
    ClanShopItem("char_sking_all",     "🟨 Персонаж strong_king всем","Случайный strong_king всем",15_000_000, "character", "character", "strong_king"),
    ClanShopItem("char_genzero_all",   "🟧 Персонаж gen_zero всем",  "Случайный gen_zero всем",  30_000_000,  "character", "character", "gen_zero"),
    ClanShopItem("char_newlegend_all", "🟥 Персонаж new_legend всем","Случайный new_legend всем",60_000_000,  "character", "character", "new_legend"),

    # ── Аукцион ───────────────────────────────────────────────────────────────
    ClanShopItem("auction_common",    "🏛 Аукцион (обычный)",    "Аукцион обычного тира",    1_000_000,  "auction", "auction", "common"),
    ClanShopItem("auction_rare",      "🏛 Аукцион (редкий)",     "Аукцион редкого тира",     3_000_000,  "auction", "auction", "rare"),
    ClanShopItem("auction_epic",      "🏛 Аукцион (эпический)",  "Аукцион эпического тира",  8_000_000,  "auction", "auction", "epic"),
]

CLAN_SHOP_MAP: dict[str, ClanShopItem] = {i.item_id: i for i in CLAN_SHOP_ITEMS}

# ── Аукционные призы (без очков/фрагментов/легенд+) ───────────────────────────
CLAN_AUCTION_REWARDS = {
    "common": [
        {"type": "coins",     "amount": 1_000_000,  "label": "💰 1M NHCoin"},
        {"type": "coins",     "amount": 2_000_000,  "label": "💰 2M NHCoin"},
        {"type": "tickets",   "amount": 3,           "label": "🎟 3 тикета"},
        {"type": "potion",    "potion_id": "potion_combat",   "label": "⚔️ Зелье силы"},
        {"type": "potion",    "potion_id": "potion_income",   "label": "💰 Зелье богатства"},
        {"type": "squad",     "rank": "SS",  "amount": 50,  "label": "💠 50×SS статистов"},
    ],
    "rare": [
        {"type": "coins",     "amount": 5_000_000,  "label": "💰 5M NHCoin"},
        {"type": "coins",     "amount": 10_000_000, "label": "💰 10M NHCoin"},
        {"type": "tickets",   "amount": 5,           "label": "🎟 5 тикетов"},
        {"type": "squad",     "rank": "SSS", "amount": 30,  "label": "🔷 30×SSS статистов"},
        {"type": "squad",     "rank": "SR",  "amount": 10,  "label": "🌟 10×SR статистов"},
        {"type": "character", "rank": "king",        "label": "🟩 Персонаж King"},
        {"type": "character", "rank": "strong_king", "label": "🟨 Персонаж Strong King"},
    ],
    "epic": [
        {"type": "coins",     "amount": 30_000_000, "label": "💰 30M NHCoin"},
        {"type": "tickets",   "amount": 10,          "label": "🎟 10 тикетов"},
        {"type": "squad",     "rank": "SSR", "amount": 10,  "label": "✨ 10×SSR статистов"},
        {"type": "squad",     "rank": "UR",  "amount": 5,   "label": "💎 5×UR статистов"},
        {"type": "character", "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        {"type": "character", "rank": "new_legend",  "label": "🟥 Персонаж New Legend"},
    ],
}