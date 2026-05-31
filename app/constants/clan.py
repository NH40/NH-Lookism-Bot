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
    circles_field: str   # поле в Clan для счётчика кругов
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
    ClanShopItem("tickets_1_all",  "🎟 1 тикет всем",   "Выдать 1 тикет всем",   15_000_000,   "tickets", "tickets", 1),
    ClanShopItem("tickets_3_all",  "🎟 3 тикета всем",  "Выдать 3 тикета всем",  40_000_000,   "tickets", "tickets", 3),
    ClanShopItem("tickets_5_all",  "🎟 5 тикетов всем", "Выдать 5 тикетов всем", 55_000_000,   "tickets", "tickets", 5),
    ClanShopItem("tickets_10_all", "🎟 10 тикетов всем","Выдать 10 тикетов всем",100_000_000, "tickets", "tickets", 10),

    # ── Зелья (все тиры I–VI из MG_TIERS, для всех участников клана) ───────────
    # Цена = индивидуальная цена × 5
    ClanShopItem("cpotion_mg_power_1",   "⚔️ Зелье силы I всем",        "Мощь +30%, 30 мин всем",          100_000, "potions", "potion", "mg_power_1"),
    ClanShopItem("cpotion_mg_power_2",   "⚔️ Зелье силы II всем",       "Мощь +50%, 30 мин всем",          300_000, "potions", "potion", "mg_power_2"),
    ClanShopItem("cpotion_mg_power_3",   "⚔️ Зелье силы III всем",      "Мощь +75%, 30 мин всем",          900_000, "potions", "potion", "mg_power_3"),
    ClanShopItem("cpotion_mg_power_4",   "⚔️ Зелье силы IV всем",       "Мощь +100%, 30 мин всем",       2_700_000, "potions", "potion", "mg_power_4"),
    ClanShopItem("cpotion_mg_power_5",   "⚔️ Зелье силы V всем",        "Мощь +125%, 30 мин всем",       8_000_000, "potions", "potion", "mg_power_5"),
    ClanShopItem("cpotion_mg_power_6",   "⚔️ Зелье силы VI всем",       "Мощь +150%, 30 мин всем",      25_000_000, "potions", "potion", "mg_power_6"),

    ClanShopItem("cpotion_mg_train_1",   "🏋 Зелье тренировки I всем",  "Тренировка +25%, 60 мин всем",    75_000, "potions", "potion", "mg_train_1"),
    ClanShopItem("cpotion_mg_train_2",   "🏋 Зелье тренировки II всем", "Тренировка +38%, 60 мин всем",   225_000, "potions", "potion", "mg_train_2"),
    ClanShopItem("cpotion_mg_train_3",   "🏋 Зелье тренировки III всем","Тренировка +55%, 60 мин всем",   675_000, "potions", "potion", "mg_train_3"),
    ClanShopItem("cpotion_mg_train_4",   "🏋 Зелье тренировки IV всем", "Тренировка +75%, 60 мин всем", 2_000_000, "potions", "potion", "mg_train_4"),
    ClanShopItem("cpotion_mg_train_5",   "🏋 Зелье тренировки V всем",  "Тренировка +100%, 60 мин всем",6_000_000, "potions", "potion", "mg_train_5"),
    ClanShopItem("cpotion_mg_train_6",   "🏋 Зелье тренировки VI всем", "Тренировка +130%, 60 мин всем",18_000_000,"potions", "potion", "mg_train_6"),

    ClanShopItem("cpotion_mg_income_1",  "💰 Зелье богатства I всем",   "Доход +40%, 60 мин всем",        100_000, "potions", "potion", "mg_income_1"),
    ClanShopItem("cpotion_mg_income_2",  "💰 Зелье богатства II всем",  "Доход +70%, 60 мин всем",        300_000, "potions", "potion", "mg_income_2"),
    ClanShopItem("cpotion_mg_income_3",  "💰 Зелье богатства III всем", "Доход +105%, 60 мин всем",       900_000, "potions", "potion", "mg_income_3"),
    ClanShopItem("cpotion_mg_income_4",  "💰 Зелье богатства IV всем",  "Доход +140%, 60 мин всем",     2_700_000, "potions", "potion", "mg_income_4"),
    ClanShopItem("cpotion_mg_income_5",  "💰 Зелье богатства V всем",   "Доход +170%, 60 мин всем",     8_000_000, "potions", "potion", "mg_income_5"),
    ClanShopItem("cpotion_mg_income_6",  "💰 Зелье богатства VI всем",  "Доход +200%, 60 мин всем",    25_000_000, "potions", "potion", "mg_income_6"),

    ClanShopItem("cpotion_mg_luck_1",    "🍀 Зелье удачи I всем",       "Шанс тикета +5%, 30 мин всем",    60_000, "potions", "potion", "mg_luck_1"),
    ClanShopItem("cpotion_mg_luck_2",    "🍀 Зелье удачи II всем",      "Шанс тикета +9%, 30 мин всем",   180_000, "potions", "potion", "mg_luck_2"),
    ClanShopItem("cpotion_mg_luck_3",    "🍀 Зелье удачи III всем",     "Шанс тикета +13%, 30 мин всем",  550_000, "potions", "potion", "mg_luck_3"),
    ClanShopItem("cpotion_mg_luck_4",    "🍀 Зелье удачи IV всем",      "Шанс тикета +17%, 30 мин всем",1_650_000, "potions", "potion", "mg_luck_4"),
    ClanShopItem("cpotion_mg_luck_5",    "🍀 Зелье удачи V всем",       "Шанс тикета +21%, 30 мин всем",4_950_000, "potions", "potion", "mg_luck_5"),
    ClanShopItem("cpotion_mg_luck_6",    "🍀 Зелье удачи VI всем",      "Шанс тикета +25%, 30 мин всем",15_000_000,"potions", "potion", "mg_luck_6"),

    ClanShopItem("cpotion_mg_infl_1",    "⚡ Зелье влияния I всем",     "Влияние +40%, 45 мин всем",       90_000, "potions", "potion", "mg_infl_1"),
    ClanShopItem("cpotion_mg_infl_2",    "⚡ Зелье влияния II всем",    "Влияние +60%, 45 мин всем",      270_000, "potions", "potion", "mg_infl_2"),
    ClanShopItem("cpotion_mg_infl_3",    "⚡ Зелье влияния III всем",   "Влияние +85%, 45 мин всем",      800_000, "potions", "potion", "mg_infl_3"),
    ClanShopItem("cpotion_mg_infl_4",    "⚡ Зелье влияния IV всем",    "Влияние +115%, 45 мин всем",   2_400_000, "potions", "potion", "mg_infl_4"),
    ClanShopItem("cpotion_mg_infl_5",    "⚡ Зелье влияния V всем",     "Влияние +150%, 45 мин всем",   7_250_000, "potions", "potion", "mg_infl_5"),
    ClanShopItem("cpotion_mg_infl_6",    "⚡ Зелье влияния VI всем",    "Влияние +200%, 45 мин всем",  21_750_000, "potions", "potion", "mg_infl_6"),

    ClanShopItem("cpotion_mg_raid_1",    "💠 Зелье охотника I всем",    "Дроп +15%, 60 мин всем",         200_000, "potions", "potion", "mg_raid_1"),
    ClanShopItem("cpotion_mg_raid_2",    "💠 Зелье охотника II всем",   "Дроп +25%, 60 мин всем",         600_000, "potions", "potion", "mg_raid_2"),
    ClanShopItem("cpotion_mg_raid_3",    "💠 Зелье охотника III всем",  "Дроп +38%, 60 мин всем",       1_800_000, "potions", "potion", "mg_raid_3"),
    ClanShopItem("cpotion_mg_raid_4",    "💠 Зелье охотника IV всем",   "Дроп +50%, 60 мин всем",       5_400_000, "potions", "potion", "mg_raid_4"),
    ClanShopItem("cpotion_mg_raid_5",    "💠 Зелье охотника V всем",    "Дроп +62%, 60 мин всем",      16_200_000, "potions", "potion", "mg_raid_5"),
    ClanShopItem("cpotion_mg_raid_6",    "💠 Зелье охотника VI всем",   "Дроп +75%, 60 мин всем",      48_500_000, "potions", "potion", "mg_raid_6"),

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
    # Обычный аукцион — зелья тира 1–2
    "common": [
        {"type": "coins",   "amount": 4_000_000,  "label": "💰 4M NHCoin"},
        {"type": "coins",   "amount": 7_000_000,  "label": "💰 7M NHCoin"},
        {"type": "tickets", "amount": 5,           "label": "🎟 5 тикетов"},
        {"type": "tickets", "amount": 8,           "label": "🎟 8 тикетов"},
        {"type": "squad",   "rank": "SSS", "amount": 200, "label": "🔷 200×SSS статистов"},
        {"type": "squad",   "rank": "SR",  "amount": 75,  "label": "🌟 75×SR статистов"},
        {"type": "potion",  "potion_id": "mg_power_2",    "label": "⚔️ Зелье силы II (+50%, 30 мин)"},
        {"type": "potion",  "potion_id": "mg_income_2",   "label": "💰 Зелье богатства II (+70%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_train_2",    "label": "🏋 Зелье тренировки II (+38%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_luck_2",     "label": "🍀 Зелье удачи II (+9%, 30 мин)"},
    ],
    # Редкий аукцион — зелья тира 3–4
    "rare": [
        {"type": "coins",          "amount": 20_000_000,  "label": "💰 20M NHCoin"},
        {"type": "coins",          "amount": 35_000_000,  "label": "💰 35M NHCoin"},
        {"type": "tickets",        "amount": 12,           "label": "🎟 12 тикетов"},
        {"type": "tickets",        "amount": 18,           "label": "🎟 18 тикетов"},
        {"type": "squad",          "rank": "SSR", "amount": 75,  "label": "✨ 75×SSR статистов"},
        {"type": "squad",          "rank": "UR",  "amount": 30,  "label": "💎 30×UR статистов"},
        {"type": "character",      "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        {"type": "character",      "rank": "strong_king", "label": "🟨 Персонаж Strong King"},
        {"type": "mastery_points", "amount": 15,          "label": "🏅 15 очков мастерства"},
        {"type": "potion",  "potion_id": "mg_power_4",    "label": "⚔️ Зелье силы IV (+100%, 30 мин)"},
        {"type": "potion",  "potion_id": "mg_income_4",   "label": "💰 Зелье богатства IV (+140%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_infl_4",     "label": "⚡ Зелье влияния IV (+115%, 45 мин)"},
        {"type": "potion",  "potion_id": "mg_raid_3",     "label": "💠 Зелье охотника III (+38%, 60 мин)"},
    ],
    # Эпический аукцион — зелья тира 5–6
    "epic": [
        {"type": "coins",          "amount": 100_000_000, "label": "💰 100M NHCoin"},
        {"type": "coins",          "amount": 150_000_000, "label": "💰 150M NHCoin"},
        {"type": "tickets",        "amount": 25,           "label": "🎟 25 тикетов"},
        {"type": "squad",          "rank": "LR",  "amount": 25,  "label": "👑 25×LR статистов"},
        {"type": "squad",          "rank": "MP",  "amount": 10,  "label": "🔱 10×MP статистов"},
        {"type": "character",      "rank": "new_legend",  "label": "🟥 Персонаж New Legend"},
        {"type": "character",      "rank": "gen_zero",    "label": "🟧 Персонаж Gen Zero"},
        {"type": "mastery_points", "amount": 40,          "label": "🏅 40 очков мастерства"},
        {"type": "potion",  "potion_id": "mg_power_6",    "label": "⚔️ Зелье силы VI (+150%, 30 мин)"},
        {"type": "potion",  "potion_id": "mg_income_6",   "label": "💰 Зелье богатства VI (+200%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_train_6",    "label": "🏋 Зелье тренировки VI (+130%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_raid_5",     "label": "💠 Зелье охотника V (+62%, 60 мин)"},
        {"type": "potion",  "potion_id": "mg_luck_6",     "label": "🍀 Зелье удачи VI (+25%, 30 мин)"},
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