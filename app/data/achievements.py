from dataclasses import dataclass

@dataclass(frozen=True)
class Achievement:
    achievement_id: str
    name: str
    description: str
    condition_key: str
    condition_value: int
    bonus_description: str
    bonus_key: str
    bonus_value: int
    secret: bool = False
    parent_id: Optional[str] = None
    permanent: bool = True  # ← бонус сохраняется после вайпа

ACHIEVEMENTS: list[Achievement] = [
    # ── Боевая сила ─────────────────────────────────────────────────────────
    Achievement("power_10k",    "Восходящий",   "⚔️", "Достигни 10,000 боевой мощи",   False, 5000,   2,  "combat_power", 10000,   "gte"),
    Achievement("power_50k",    "Грозный",      "⚔️", "Достигни 50,000 боевой мощи",   False, 20000,  5,  "combat_power", 50000,   "gte"),
    Achievement("power_100k",   "Легенда",      "⚔️", "Достигни 100,000 боевой мощи",  False, 50000,  10, "combat_power", 100000,  "gte"),
    Achievement("power_1m",     "Бог войны",    "💀", "Достигни 1,000,000 боевой мощи",False, 200000, 20, "combat_power", 1000000, "gte"),

    # ── Фазы ────────────────────────────────────────────────────────────────
    Achievement("phase_king",     "Король",        "👑", "Стань Королём",     False, 10000,  5,  "phase", 0, "phase"),
    Achievement("phase_fist",     "Кулак",         "✊", "Стань Кулаком",     False, 30000,  10, "phase", 0, "phase"),
    Achievement("fist_10cities",  "Завоеватель",   "🏙", "Захвати 10 городов кулака", False, 50000, 15, "fist_cities_count", 10, "gte"),
    Achievement("phase_emperor",  "Император",     "🏛", "Стань Императором", False, 100000, 25, "phase", 0, "phase"),

    # ── Победы ──────────────────────────────────────────────────────────────
    Achievement("wins_10",  "Боец",    "🥊", "Победи в 10 боях",  False, 2000, 1, "total_wins", 10,  "gte"),
    Achievement("wins_100", "Ветеран", "🏆", "Победи в 100 боях", False, 10000, 3, "total_wins", 100, "gte"),

    # ── Траты ───────────────────────────────────────────────────────────────
    Achievement("spend_100k", "Транжира",  "💸", "Потрать 100,000 NHCoin", False, 5000,  2, "coins_spent", 100000,  "gte"),
    Achievement("spend_1m",   "Богач",     "💰", "Потрать 1,000,000 NHCoin",False,20000,  5, "coins_spent", 1000000, "gte"),

    # ── Аукцион ─────────────────────────────────────────────────────────────
    Achievement("auction_1", "Участник", "🏛", "Победи на аукционе",   False, 3000, 2, "auction_wins", 1, "gte"),
    Achievement("auction_5", "Коллекционер","💎","Победи на 5 аукционах",False,15000, 5, "auction_wins", 5, "gte"),

    # ── Топ ─────────────────────────────────────────────────────────────────
    Achievement("top_10", "Элита",    "🔝", "Войди в топ-10 по мощи", False, 20000, 5,  None, None, "top"),
    Achievement("top_5",  "Мастер",   "⭐", "Войди в топ-5 по мощи",  False, 50000, 10, None, None, "top"),
    Achievement("top_1",  "Сильнейший","🥇","Стань #1 по мощи",       False, 100000,20, None, None, "top"),

    # ── Коллекция ───────────────────────────────────────────────────────────
    Achievement("all_regular", "Коллекционер+", "📦", "Получи все несекретные достижения", False, 50000, 10, None, None, "special"),
    Achievement("absolute",    "Абсолют",        "🌟", "Получи все достижения",             False, 200000,30, None, None, "special"),

    # ── Секретные ───────────────────────────────────────────────────────────
    Achievement("settings_100",  "???", "🔐", "Открой настройки 100 раз",  True, 5000,  2, "settings_opened", 100, "gte"),
    Achievement("settings_500",  "???", "🔏", "Открой настройки 500 раз",  True, 20000, 5, "settings_opened", 500, "gte"),
    Achievement("shadow_syndicate","???","🕶", "Построй Синдикат",           True, 30000, 8, None, None, "special"),
    Achievement("future_masterpiece","???","🎨","Будущий шедевр",            True, 50000, 10,None, None, "special"),
]

ACHIEVEMENTS_BY_ID: dict[str, Achievement] = {a.achievement_id: a for a in ACHIEVEMENTS}