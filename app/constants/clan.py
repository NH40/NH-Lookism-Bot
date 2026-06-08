from dataclasses import dataclass


MAX_DONAT_CIRCLES = 5

@dataclass(frozen=True)
class ClanDonatPackage:
    package_id: str
    name: str
    desc: str
    price_rub: int
    income_pct: int
    ticket_pct: int
    train_pct: int
    circles_field: str
    max_circles: int = MAX_DONAT_CIRCLES


CLAN_DONAT_PACKAGES: list[ClanDonatPackage] = [
    ClanDonatPackage("donat_income",  "💰 Богатство клана", "+10% к доходу всем участникам",                500,  10, 0,  0,  "donat_wealth_circles"),
    ClanDonatPackage("donat_ticket",  "🍀 Удача клана",     "+5% к шансу тикета всем участникам",           400,  0,  5,  0,  "donat_luck_circles"),
    ClanDonatPackage("donat_train",   "🏋️ Школа клана",    "+10% к охвату тренировки всем участникам",     350,  0,  0,  10, "donat_school_circles"),
    ClanDonatPackage("donat_war",     "⚔️ Клан Войн",       "+10% к доходу + +10% к тренировкам всем",      900,  10, 0,  10, "donat_war_circles"),
    ClanDonatPackage("donat_premium", "👑 Премиум клан",    "+15% к доходу + +5% к тикетам + +10% к трен.", 1500, 15, 5,  10, "donat_premium_circles"),
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
    max_total: int

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

    # ── Тикеты — цены БЕЗ ИЗМЕНЕНИЙ (барьер накопления богатства) ─────────────
    ClanShopItem("tickets_1_all",  "🎟 1 тикет всем",   "Выдать 1 тикет всем",    15_000_000,  "tickets", "tickets", 1),
    ClanShopItem("tickets_3_all",  "🎟 3 тикета всем",  "Выдать 3 тикета всем",   40_000_000,  "tickets", "tickets", 3),
    ClanShopItem("tickets_5_all",  "🎟 5 тикетов всем", "Выдать 5 тикетов всем",  55_000_000,  "tickets", "tickets", 5),
    ClanShopItem("tickets_10_all", "🎟 10 тикетов всем","Выдать 10 тикетов всем",100_000_000,  "tickets", "tickets", 10),

    # ── Зелья (÷3 — ежедневный расходник, должен быть доступен) ──────────────
    ClanShopItem("cpotion_mg_power_1",   "⚔️ Зелье силы I всем",        "Мощь +20%, 30 мин всем",           33_000, "potions", "potion", "mg_power_1"),
    ClanShopItem("cpotion_mg_power_2",   "⚔️ Зелье силы II всем",       "Мощь +40%, 30 мин всем",          100_000, "potions", "potion", "mg_power_2"),
    ClanShopItem("cpotion_mg_power_3",   "⚔️ Зелье силы III всем",      "Мощь +60%, 30 мин всем",          300_000, "potions", "potion", "mg_power_3"),
    ClanShopItem("cpotion_mg_power_4",   "⚔️ Зелье силы IV всем",       "Мощь +80%, 30 мин всем",          900_000, "potions", "potion", "mg_power_4"),
    ClanShopItem("cpotion_mg_power_5",   "⚔️ Зелье силы V всем",        "Мощь +100%, 30 мин всем",       2_665_000, "potions", "potion", "mg_power_5"),
    ClanShopItem("cpotion_mg_power_6",   "⚔️ Зелье силы VI всем",       "Мощь +120%, 30 мин всем",       8_335_000, "potions", "potion", "mg_power_6"),

    ClanShopItem("cpotion_mg_train_1",   "🏋 Зелье тренировки I всем",  "Тренировка +20%, 60 мин всем",     25_000, "potions", "potion", "mg_train_1"),
    ClanShopItem("cpotion_mg_train_2",   "🏋 Зелье тренировки II всем", "Тренировка +35%, 60 мин всем",     75_000, "potions", "potion", "mg_train_2"),
    ClanShopItem("cpotion_mg_train_3",   "🏋 Зелье тренировки III всем","Тренировка +55%, 60 мин всем",    225_000, "potions", "potion", "mg_train_3"),
    ClanShopItem("cpotion_mg_train_4",   "🏋 Зелье тренировки IV всем", "Тренировка +75%, 60 мин всем",    665_000, "potions", "potion", "mg_train_4"),
    ClanShopItem("cpotion_mg_train_5",   "🏋 Зелье тренировки V всем",  "Тренировка +95%, 60 мин всем",  2_000_000, "potions", "potion", "mg_train_5"),
    ClanShopItem("cpotion_mg_train_6",   "🏋 Зелье тренировки VI всем", "Тренировка +120%, 60 мин всем", 6_000_000, "potions", "potion", "mg_train_6"),

    ClanShopItem("cpotion_mg_income_1",  "💰 Зелье богатства I всем",   "Доход +20%, 60 мин всем",          33_000, "potions", "potion", "mg_income_1"),
    ClanShopItem("cpotion_mg_income_2",  "💰 Зелье богатства II всем",  "Доход +40%, 60 мин всем",         100_000, "potions", "potion", "mg_income_2"),
    ClanShopItem("cpotion_mg_income_3",  "💰 Зелье богатства III всем", "Доход +65%, 60 мин всем",         300_000, "potions", "potion", "mg_income_3"),
    ClanShopItem("cpotion_mg_income_4",  "💰 Зелье богатства IV всем",  "Доход +85%, 60 мин всем",         900_000, "potions", "potion", "mg_income_4"),
    ClanShopItem("cpotion_mg_income_5",  "💰 Зелье богатства V всем",   "Доход +100%, 60 мин всем",      2_665_000, "potions", "potion", "mg_income_5"),
    ClanShopItem("cpotion_mg_income_6",  "💰 Зелье богатства VI всем",  "Доход +120%, 60 мин всем",      8_335_000, "potions", "potion", "mg_income_6"),

    ClanShopItem("cpotion_mg_luck_1",    "🍀 Зелье удачи I всем",       "Шанс тикета +5%, 30 мин всем",     20_000, "potions", "potion", "mg_luck_1"),
    ClanShopItem("cpotion_mg_luck_2",    "🍀 Зелье удачи II всем",      "Шанс тикета +9%, 30 мин всем",     60_000, "potions", "potion", "mg_luck_2"),
    ClanShopItem("cpotion_mg_luck_3",    "🍀 Зелье удачи III всем",     "Шанс тикета +13%, 30 мин всем",   183_000, "potions", "potion", "mg_luck_3"),
    ClanShopItem("cpotion_mg_luck_4",    "🍀 Зелье удачи IV всем",      "Шанс тикета +17%, 30 мин всем",   550_000, "potions", "potion", "mg_luck_4"),
    ClanShopItem("cpotion_mg_luck_5",    "🍀 Зелье удачи V всем",       "Шанс тикета +21%, 30 мин всем",  1_650_000, "potions", "potion", "mg_luck_5"),
    ClanShopItem("cpotion_mg_luck_6",    "🍀 Зелье удачи VI всем",      "Шанс тикета +25%, 30 мин всем",  5_000_000, "potions", "potion", "mg_luck_6"),

    ClanShopItem("cpotion_mg_infl_1",    "⚡ Зелье влияния I всем",     "Влияние +20%, 45 мин всем",        30_000, "potions", "potion", "mg_infl_1"),
    ClanShopItem("cpotion_mg_infl_2",    "⚡ Зелье влияния II всем",    "Влияние +40%, 45 мин всем",        90_000, "potions", "potion", "mg_infl_2"),
    ClanShopItem("cpotion_mg_infl_3",    "⚡ Зелье влияния III всем",   "Влияние +65%, 45 мин всем",       265_000, "potions", "potion", "mg_infl_3"),
    ClanShopItem("cpotion_mg_infl_4",    "⚡ Зелье влияния IV всем",    "Влияние +90%, 45 мин всем",       800_000, "potions", "potion", "mg_infl_4"),
    ClanShopItem("cpotion_mg_infl_5",    "⚡ Зелье влияния V всем",     "Влияние +105%, 45 мин всем",    2_415_000, "potions", "potion", "mg_infl_5"),
    ClanShopItem("cpotion_mg_infl_6",    "⚡ Зелье влияния VI всем",    "Влияние +120%, 45 мин всем",    7_250_000, "potions", "potion", "mg_infl_6"),

    ClanShopItem("cpotion_mg_raid_1",    "💠 Зелье охотника I всем",    "Дроп +15%, 60 мин всем",           67_000, "potions", "potion", "mg_raid_1"),
    ClanShopItem("cpotion_mg_raid_2",    "💠 Зелье охотника II всем",   "Дроп +25%, 60 мин всем",          200_000, "potions", "potion", "mg_raid_2"),
    ClanShopItem("cpotion_mg_raid_3",    "💠 Зелье охотника III всем",  "Дроп +38%, 60 мин всем",          600_000, "potions", "potion", "mg_raid_3"),
    ClanShopItem("cpotion_mg_raid_4",    "💠 Зелье охотника IV всем",   "Дроп +50%, 60 мин всем",        1_800_000, "potions", "potion", "mg_raid_4"),
    ClanShopItem("cpotion_mg_raid_5",    "💠 Зелье охотника V всем",    "Дроп +62%, 60 мин всем",        5_400_000, "potions", "potion", "mg_raid_5"),
    ClanShopItem("cpotion_mg_raid_6",    "💠 Зелье охотника VI всем",   "Дроп +75%, 60 мин всем",       16_165_000, "potions", "potion", "mg_raid_6"),

    # ── Статисты (÷2 — армия должна стоить усилий) ────────────────────────────
    ClanShopItem("squad_s_all",   "🟥 100×S всем",    "100 статистов S всем",      450_000,  "squad", "squad", {"rank": "S",   "amount": 100}),
    ClanShopItem("squad_ss_all",  "💠 100×SS всем",   "100 статистов SS всем",     500_000,  "squad", "squad", {"rank": "SS",  "amount": 100}),
    ClanShopItem("squad_sss_all", "🔷 100×SSS всем",  "100 статистов SSS всем",    750_000,  "squad", "squad", {"rank": "SSS", "amount": 100}),
    ClanShopItem("squad_sr_all",  "🌟 100×SR всем",   "100 статистов SR всем",   1_100_000,  "squad", "squad", {"rank": "SR",  "amount": 100}),
    ClanShopItem("squad_ssr_all", "✨ 100×SSR всем",  "100 статистов SSR всем",  1_250_000,  "squad", "squad", {"rank": "SSR", "amount": 100}),
    ClanShopItem("squad_ur_all",  "💎 100×UR всем",   "100 статистов UR всем",   1_500_000,  "squad", "squad", {"rank": "UR",  "amount": 100}),
    ClanShopItem("squad_lr_all",  "👑 100×LR всем",   "100 статистов LR всем",   2_500_000,  "squad", "squad", {"rank": "LR",  "amount": 100}),
    ClanShopItem("squad_mp_all",  "🔱 100×MP всем",   "100 статистов MP всем",   4_000_000,  "squad", "squad", {"rank": "MP",  "amount": 100}),
    ClanShopItem("squad_x_all",   "⚡ 100×X всем",    "100 статистов X всем",    6_000_000,  "squad", "squad", {"rank": "X",   "amount": 100}),
    ClanShopItem("squad_xx_all",  "🌀 100×XX всем",   "100 статистов XX всем",   9_000_000,  "squad", "squad", {"rank": "XX",  "amount": 100}),
    ClanShopItem("squad_xxx_all", "🔥 100×XXX всем",  "100 статистов XXX всем", 12_500_000,  "squad", "squad", {"rank": "XXX", "amount": 100}),
    ClanShopItem("squad_dx_all",  "💀 100×DX всем",   "100 статистов DX всем",  17_500_000,  "squad", "squad", {"rank": "DX",  "amount": 100}),
    ClanShopItem("squad_err_all", "❌ 100×ERROR всем", "100 ERROR всем",         25_000_000,  "squad", "squad", {"rank": "ERROR","amount": 100}),

    # ── Персонажи (÷2 — цель для сохранения) ──────────────────────────────────
    ClanShopItem("char_member_all",    "⬜ Персонаж member всем",    "Случайный member всем",      1_000_000,  "character", "character", "member"),
    ClanShopItem("char_boss_all",      "🟦 Персонаж boss всем",      "Случайный boss всем",        2_000_000,  "character", "character", "boss"),
    ClanShopItem("char_king_all",      "🟩 Персонаж king всем",      "Случайный king всем",        4_000_000,  "character", "character", "king"),
    ClanShopItem("char_sking_all",     "🟨 Персонаж strong_king всем","Случайный strong_king всем", 7_500_000, "character", "character", "strong_king"),
    ClanShopItem("char_genzero_all",   "🟧 Персонаж gen_zero всем",  "Случайный gen_zero всем",   15_000_000,  "character", "character", "gen_zero"),
    ClanShopItem("char_newlegend_all", "🟥 Персонаж new_legend всем","Случайный new_legend всем", 30_000_000,  "character", "character", "new_legend"),

    # ── Аукцион (÷2 — значимая инвестиция клана) ──────────────────────────────
    ClanShopItem("auction_common",    "🏛 Аукцион (обычный)",    "Аукцион обычного тира",    2_750_000,  "auction", "auction", "common"),
    ClanShopItem("auction_rare",      "🏛 Аукцион (редкий)",     "Аукцион редкого тира",     7_750_000,  "auction", "auction", "rare"),
    ClanShopItem("auction_epic",      "🏛 Аукцион (эпический)",  "Аукцион эпического тира", 25_000_000,  "auction", "auction", "epic"),
]

CLAN_SHOP_MAP: dict[str, ClanShopItem] = {i.item_id: i for i in CLAN_SHOP_ITEMS}

# ── Аукционные призы — монетные награды ÷2, тикеты и предметы без изменений ──
CLAN_AUCTION_REWARDS = {
    "common": [
        {"type": "coins",   "amount": 2_000_000,  "label": "💰 2M NHCoin"},
        {"type": "coins",   "amount": 3_500_000,  "label": "💰 3.5M NHCoin"},
        {"type": "tickets", "amount": 5,           "label": "🎟 5 тикетов"},
        {"type": "tickets", "amount": 8,           "label": "🎟 8 тикетов"},
        {"type": "squad",   "rank": "SSS", "amount": 200, "label": "🔷 200×SSS статистов"},
        {"type": "squad",   "rank": "SR",  "amount": 75,  "label": "🌟 75×SR статистов"},
        {"type": "potion",  "potion_id": "mg_power_2",    "label": "⚔️ Зелье силы II (+40%, 30 мин)"},
        {"type": "potion",  "potion_id": "mg_income_2",   "label": "💰 Зелье богатства II (+40%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_train_2",    "label": "🏋 Зелье тренировки II (+35%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_luck_2",     "label": "🍀 Зелье удачи II (+9%, 30 мин)"},
    ],
    "rare": [
        {"type": "coins",          "amount": 10_000_000, "label": "💰 10M NHCoin"},
        {"type": "coins",          "amount": 17_500_000, "label": "💰 17.5M NHCoin"},
        {"type": "tickets",        "amount": 12,          "label": "🎟 12 тикетов"},
        {"type": "tickets",        "amount": 18,          "label": "🎟 18 тикетов"},
        {"type": "squad",          "rank": "SSR", "amount": 75,  "label": "✨ 75×SSR статистов"},
        {"type": "squad",          "rank": "UR",  "amount": 30,  "label": "💎 30×UR статистов"},
        {"type": "character",      "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        {"type": "character",      "rank": "strong_king", "label": "🟨 Персонаж Strong King"},
        {"type": "mastery_points", "amount": 15,          "label": "🏅 15 очков мастерства"},
        {"type": "potion",  "potion_id": "mg_power_4",    "label": "⚔️ Зелье силы IV (+80%, 30 мин)"},
        {"type": "potion",  "potion_id": "mg_income_4",   "label": "💰 Зелье богатства IV (+85%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_infl_4",     "label": "⚡ Зелье влияния IV (+90%, 45 мин)"},
        {"type": "potion",  "potion_id": "mg_raid_3",     "label": "💠 Зелье охотника III (+38%, 60 мин)"},
    ],
    "epic": [
        {"type": "coins",          "amount": 50_000_000, "label": "💰 50M NHCoin"},
        {"type": "coins",          "amount": 75_000_000, "label": "💰 75M NHCoin"},
        {"type": "tickets",        "amount": 25,          "label": "🎟 25 тикетов"},
        {"type": "squad",          "rank": "LR",  "amount": 25,  "label": "👑 25×LR статистов"},
        {"type": "squad",          "rank": "MP",  "amount": 10,  "label": "🔱 10×MP статистов"},
        {"type": "character",      "rank": "new_legend",  "label": "🟥 Персонаж New Legend"},
        {"type": "character",      "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        {"type": "mastery_points", "amount": 40,          "label": "🏅 40 очков мастерства"},
        {"type": "potion",  "potion_id": "mg_power_6",    "label": "⚔️ Зелье силы VI (+120%, 30 мин)"},
        {"type": "potion",  "potion_id": "mg_income_6",   "label": "💰 Зелье богатства VI (+120%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_train_6",    "label": "🏋 Зелье тренировки VI (+120%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_raid_5",     "label": "💠 Зелье охотника V (+62%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_luck_6",     "label": "🍀 Зелье удачи VI (+25%, 30 мин)"},
    ],
}

# Апгрейды ÷2 — значимые, но достижимые цели для клана
CLAN_UPGRADES: list[ClanUpgrade] = [
    ClanUpgrade("slot_1",  "👤 +1 место",   "+1 слот для участника",    1_250_000,  "upgrades", "slots", 1,  25),
    ClanUpgrade("slot_3",  "👥 +3 места",   "+3 слота для участников",  2_500_000,  "upgrades", "slots", 3,  25),
    ClanUpgrade("slot_5",  "👥 +5 мест",    "+5 слотов для участников", 5_000_000,  "upgrades", "slots", 5,  25),
    ClanUpgrade("slot_10", "👥 +10 мест",   "+10 слотов",               7_500_000,  "upgrades", "slots", 10, 25),

    ClanUpgrade("mult_income",  "💰 Доход +5%",      "+5% к доходу всем участникам",       2_000_000, "upgrades", "income",  5, 1),
    ClanUpgrade("mult_ticket",  "🎟 Тикет +5%",      "+5% к шансу тикета всем участникам", 4_000_000, "upgrades", "ticket",  5, 1),
    ClanUpgrade("mult_train",   "🏋 Тренировка +5%", "+5% к тренировкам всем участникам",  1_000_000, "upgrades", "train",   5, 1),
]

CLAN_UPGRADES_MAP: dict[str, ClanUpgrade] = {u.upgrade_id: u for u in CLAN_UPGRADES}
