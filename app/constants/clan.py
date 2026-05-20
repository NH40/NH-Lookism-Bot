from dataclasses import dataclass


@dataclass(frozen=True)
class ClanDonatPackage:
    package_id: str
    name: str
    desc: str
    price_rub: int
    income_pct: int
    ticket_pct: int
    train_pct: int


CLAN_DONAT_PACKAGES: list[ClanDonatPackage] = [
    ClanDonatPackage("donat_income",  "💰 Богатство клана", "+20% к доходу всем участникам",               500,  20, 0,  0 ),
    ClanDonatPackage("donat_ticket",  "🍀 Удача клана",     "+10% к шансу тикета всем участникам",          400,  0,  10, 0 ),
    ClanDonatPackage("donat_train",   "🏋 Школа клана",     "+20% к охвату тренировки всем участникам",     350,  0,  0,  20),
    ClanDonatPackage("donat_war",     "⚔️ Клан Войн",       "+20% к доходу + +20% к тренировкам всем",      900,  20, 0,  20),
    ClanDonatPackage("donat_premium", "👑 Премиум клан",    "+30% к доходу + +10% к тикетам + +25% к трен.",1500, 30, 10, 25),
]

CLAN_DONAT_PACKAGES_MAP: dict[str, ClanDonatPackage] = {p.package_id: p for p in CLAN_DONAT_PACKAGES}


@dataclass(frozen=True)
class ClanShopItem:
    item_id: str
    name: str
    desc: str
    price: int
    category: str
    item_type: str
    value: object

@dataclass(frozen=True)
class ClanUpgrade:
    upgrade_id: str
    name: str
    desc: str
    price: int
    category: str
    upgrade_type: str
    value: int
    max_total: int  # максимум суммарно на клан

# ── Категории ──────────────────────────────────────────────────────────────────
CLAN_SHOP_CATEGORIES = {
    "tickets":   "🎟 Тикеты",
    "potions":   "🧪 Зелья",
    "squad":     "👥 Статисты",
    "character": "🎴 Персонажи",
    "auction":   "🏛 Аукцион",
    "upgrades":  "⚙️ Улучшения клана",
    "donate":    "💎 Донат",
}

CLAN_SHOP_ITEMS: list[ClanShopItem] = [

    # ── Тикеты ────────────────────────────────────────────────────────────────
    ClanShopItem("tickets_1_all",  "🎟 1 тикет всем",   "Выдать 1 тикет всем",   3_750_000,   "tickets", "tickets", 1),
    ClanShopItem("tickets_3_all",  "🎟 3 тикета всем",  "Выдать 3 тикета всем",  10_000_000,   "tickets", "tickets", 3),
    ClanShopItem("tickets_5_all",  "🎟 5 тикетов всем", "Выдать 5 тикетов всем", 15_000_000,   "tickets", "tickets", 5),
    ClanShopItem("tickets_10_all", "🎟 10 тикетов всем","Выдать 10 тикетов всем",25_000_000, "tickets", "tickets", 10),

    # ── Зелья ─────────────────────────────────────────────────────────────────
    ClanShopItem("potion_combat_all",    "⚔️ Зелье силы всем",       "Боевая мощь +30% на 30 мин всем",     125_000, "potions", "potion", "potion_combat"),
    ClanShopItem("potion_income_all",    "💰 Зелье богатства всем",  "Доход +50% на 60 мин всем",           500_000,   "potions", "potion", "potion_income"),
    ClanShopItem("potion_influence_all", "⚡ Зелье влияния всем",    "Влияние +40% на 45 мин всем",         90_000,   "potions", "potion", "potion_influence"),
    ClanShopItem("potion_training_all",  "🏋 Зелье тренировки всем", "Охват тренировки +25% на 60 мин всем",65_000,  "potions", "potion", "potion_training"),
    ClanShopItem("potion_luck_all",      "🍀 Зелье удачи всем",      "Шанс тикета +20% на 30 мин всем",     60_000,   "potions", "potion", "potion_luck"),

    # ── Статисты ──────────────────────────────────────────────────────────────
    ClanShopItem("squad_s_all",   "🟥 100×S всем",    "100 статистов S всем",    900_000,   "squad", "squad", {"rank": "S",   "amount": 100}),
    ClanShopItem("squad_ss_all",  "💠 100×SS всем",   "100 статистов SS всем",   1_000_000, "squad", "squad", {"rank": "SS",  "amount": 100}),
    ClanShopItem("squad_sss_all", "🔷 100×SSS всем",  "100 статистов SSS всем",  1_500_000, "squad", "squad", {"rank": "SSS", "amount": 100}),
    ClanShopItem("squad_sr_all",  "🌟 100×SR всем",   "100 статистов SR всем",   2_200_000, "squad", "squad", {"rank": "SR",  "amount": 100}),
    ClanShopItem("squad_ssr_all", "✨ 100×SSR всем",  "100 статистов SSR всем",  2_500_000, "squad", "squad", {"rank": "SSR", "amount": 100}),
    ClanShopItem("squad_ur_all",  "💎 100×UR всем",   "100 статистов UR всем",   3_000_000, "squad", "squad", {"rank": "UR",  "amount": 100}),
    ClanShopItem("squad_lr_all",  "👑 100×LR всем",   "100 статистов LR всем",   5_000_000, "squad", "squad", {"rank": "LR",  "amount": 100}),
    ClanShopItem("squad_mp_all",  "🔱 100×MP всем",    "100 статистов MP всем",    8_000_000, "squad", "squad", {"rank": "MP",  "amount": 100}),
    ClanShopItem("squad_x_all",   "⚡ 100×X всем",     "100 статистов X всем",    12_000_000, "squad", "squad", {"rank": "X",   "amount": 100}),
    ClanShopItem("squad_xx_all",  "🌀 100×XX всем",    "100 статистов XX всем",   18_000_000, "squad", "squad", {"rank": "XX",  "amount": 100}),
    ClanShopItem("squad_xxx_all", "🔥 100×XXX всем",   "100 статистов XXX всем",  25_000_000, "squad", "squad", {"rank": "XXX", "amount": 100}),
    ClanShopItem("squad_dx_all",  "💀 100×DX всем",     "100 статистов DX всем",    35_000_000, "squad", "squad", {"rank": "DX",  "amount": 100}),
    ClanShopItem("squad_err_all", "❌ 100×ERROR всем",  "100 ERROR всем",            50_000_000, "squad", "squad", {"rank": "ERROR","amount": 100}),

    # ── Персонажи ─────────────────────────────────────────────────────────────
    ClanShopItem("char_member_all",    "⬜ Персонаж member всем",    "Случайный member всем",    2_000_000,   "character", "character", "member"),
    ClanShopItem("char_boss_all",      "🟦 Персонаж boss всем",      "Случайный boss всем",      4_000_000,   "character", "character", "boss"),
    ClanShopItem("char_king_all",      "🟩 Персонаж king всем",      "Случайный king всем",      8_000_000,   "character", "character", "king"),
    ClanShopItem("char_sking_all",     "🟨 Персонаж strong_king всем","Случайный strong_king всем",15_000_000, "character", "character", "strong_king"),
    ClanShopItem("char_genzero_all",   "🟧 Персонаж gen_zero всем",  "Случайный gen_zero всем",  30_000_000,  "character", "character", "gen_zero"),
    ClanShopItem("char_newlegend_all", "🟥 Персонаж new_legend всем","Случайный new_legend всем",60_000_000,  "character", "character", "new_legend"),

    # ── Аукцион ───────────────────────────────────────────────────────────────
    ClanShopItem("auction_common",    "🏛 Аукцион (обычный)",    "Аукцион обычного тира",    5_500_000,  "auction", "auction", "common"),
    ClanShopItem("auction_rare",      "🏛 Аукцион (редкий)",     "Аукцион редкого тира",     15_500_000,  "auction", "auction", "rare"),
    ClanShopItem("auction_epic",      "🏛 Аукцион (эпический)",  "Аукцион эпического тира",  50_000_000,  "auction", "auction", "epic"),
]

CLAN_SHOP_MAP: dict[str, ClanShopItem] = {i.item_id: i for i in CLAN_SHOP_ITEMS}

# ── Аукционные призы ───────────────────────────────────────────────────────────
CLAN_AUCTION_REWARDS = {
    "common": [
        {"type": "coins",   "amount": 4_000_000,  "label": "💰 4M NHCoin"},
        {"type": "coins",   "amount": 7_000_000,  "label": "💰 7M NHCoin"},
        {"type": "tickets", "amount": 5,           "label": "🎟 5 тикетов"},
        {"type": "tickets", "amount": 8,           "label": "🎟 8 тикетов"},
        {"type": "squad",   "rank": "SSS", "amount": 200, "label": "🔷 200×SSS статистов"},
        {"type": "squad",   "rank": "SR",  "amount": 75,  "label": "🌟 75×SR статистов"},
        {"type": "potion",  "potion_id": "potion_combat",  "label": "⚔️ Зелье силы"},
        {"type": "potion",  "potion_id": "potion_income",  "label": "💰 Зелье богатства"},
    ],
    "rare": [
        {"type": "coins",          "amount": 20_000_000,  "label": "💰 20M NHCoin"},
        {"type": "coins",          "amount": 35_000_000,  "label": "💰 35M NHCoin"},
        {"type": "tickets",        "amount": 12,           "label": "🎟 12 тикетов"},
        {"type": "tickets",        "amount": 18,           "label": "🎟 18 тикетов"},
        {"type": "squad",          "rank": "SSR", "amount": 75,  "label": "✨ 75×SSR статистов"},
        {"type": "squad",          "rank": "UR",  "amount": 30,  "label": "💎 30×UR статистов"},
        {"type": "character",      "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        {"type": "character",      "rank": "strong_king", "label": "🟨 Персонаж Strong King"},
        # {"type": "mastery_points", "amount": 20,          "label": "🏅 20 очков мастерства"},
    ],
    "epic": [
        {"type": "coins",          "amount": 100_000_000, "label": "💰 100M NHCoin"},
        {"type": "coins",          "amount": 150_000_000, "label": "💰 150M NHCoin"},
        {"type": "tickets",        "amount": 25,           "label": "🎟 25 тикетов"},
        {"type": "squad",          "rank": "LR",  "amount": 25,  "label": "👑 25×LR статистов"},
        {"type": "squad",          "rank": "MP",  "amount": 10,  "label": "🔱 10×MP статистов"},
        {"type": "character",      "rank": "new_legend",  "label": "🟥 Персонаж New Legend"},
        {"type": "character",      "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        # {"type": "mastery_points", "amount": 80,         "label": "🏅 80 очков мастерства"},
    ],
}

CLAN_UPGRADES: list[ClanUpgrade] = [
    # ── Места ─────────────────────────────────────────────────────────────────
    ClanUpgrade("slot_1",  "👤 +1 место",   "+1 слот для участника",   2_500_000,    "upgrades", "slots", 1,  25),
    ClanUpgrade("slot_3",  "👥 +3 места",   "+3 слота для участников", 5_000_000,  "upgrades", "slots", 3,  25),
    ClanUpgrade("slot_5",  "👥 +5 мест",    "+5 слотов для участников",10_000_000,  "upgrades", "slots", 5,  25),
    ClanUpgrade("slot_10", "👥 +10 мест",   "+10 слотов",              15_000_000,  "upgrades", "slots", 10, 25),

    # ── Множители (по 1 разу) ─────────────────────────────────────────────────
    ClanUpgrade("mult_income",  "💰 Доход +5%",      "+5% к доходу всем участникам",       4_000_000, "upgrades", "income",  5, 1),
    ClanUpgrade("mult_ticket",  "🎟 Тикет +5%",      "+5% к шансу тикета всем участникам", 8_000_000, "upgrades", "ticket",  5, 1),
    ClanUpgrade("mult_train",   "🏋 Тренировка +5%", "+5% к тренировкам всем участникам",  2_000_000, "upgrades", "train",   5, 1),
]

CLAN_UPGRADES_MAP: dict[str, ClanUpgrade] = {u.upgrade_id: u for u in CLAN_UPGRADES}