from dataclasses import dataclass
from typing import Optional


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


ACHIEVEMENTS: list[Achievement] = [
    # ─── Боевая мощь ───
    Achievement("power_10k", "Ты ещё не лысый, но уже опасный",
        "Набери 10,000 боевой мощи", "combat_power", 10_000,
        "+500 NHCoin", "coins", 500),
    Achievement("power_50k", "50к — город шепчет твоё имя",
        "Набери 50,000 боевой мощи", "combat_power", 50_000,
        "+2,000 NHCoin", "coins", 2_000, parent_id="power_10k"),
    Achievement("power_100k", "100к — легенда окраин",
        "Набери 100,000 боевой мощи", "combat_power", 100_000,
        "+10,000 NHCoin + +5% к доходу", "coins_and_income", 10_000,
        parent_id="power_50k"),
    Achievement("power_1m", "Ну ты мощный",
        "Набери 1,000,000 боевой мощи", "combat_power", 1_000_000,
        "+50,000 NHCoin + +10% к доходу", "coins_and_income_10", 50_000,
        parent_id="power_100k"),

    # ─── Фазы ───
    Achievement("first_king", "Король лужи — тоже король",
        "Стань Королём", "phase_reached", 1,
        "+7,000 NHCoin + +5% к доходу", "coins_and_income", 7_000),
    Achievement("first_fist", "Кулак — это не должность, а диагноз",
        "Стань Кулаком", "phase_reached", 2,
        "+1,500 NHCoin", "coins", 1_500),
    Achievement("fist_10_cities", "Легенда 0 поколения",
        "Захвати 10 городов в фазе Кулака", "fist_cities_count", 10,
        "+10,000 NHCoin + +5% к доходу", "coins_and_income", 10_000,
        parent_id="first_fist"),
    Achievement("emperor", "Император NH",
        "Стань Императором", "phase_reached", 3,
        "+3 очка пути", "path_points", 3),

    # ─── Топ ───
    Achievement("top_10", "Осталось выбить девятого",
        "Попади в топ-10 по боевой мощи", "top_rank", 10,
        "+10,000 NHCoin + +3% к доходу", "coins_and_income_3", 10_000),
    Achievement("top_5", "Топ-5",
        "Попади в топ-5 по боевой мощи", "top_rank", 5,
        "+30,000 NHCoin + +5% к доходу", "coins_and_income", 30_000,
        parent_id="top_10"),
    Achievement("top_1", "Топ-1",
        "Стань первым по боевой мощи", "top_rank", 1,
        "+150,000 NHCoin + +10% к доходу", "coins_and_income_10", 150_000,
        parent_id="top_5"),

    # ─── Траты ───
    Achievement("spend_100k", "Бабло не пахнет, но горит быстро",
        "Потрать 100,000 NHCoin", "coins_spent", 100_000,
        "Нет (ты уже потратил)", "none", 0),
    Achievement("spend_1m", "Инвестиционный гений",
        "Потрать 1,000,000 NHCoin", "coins_spent", 1_000_000,
        "+15,000 NHCoin + +5% к доходу", "coins_and_income", 15_000,
        parent_id="spend_100k"),

    # ─── Бои ───
    Achievement("wins_10", "Вроде неплох, но лох",
        "Выиграй 10 боёв", "total_wins", 10,
        "+300 NHCoin", "coins", 300),
    Achievement("wins_100", "Вроде лох, но ты неплох",
        "Выиграй 100 боёв", "total_wins", 100,
        "+5,000 NHCoin + +3% к доходу", "coins_and_income_3", 5_000,
        parent_id="wins_10"),

    # ─── Аукцион ───
    Achievement("auction_win_1", "Денег куры не клюют",
        "Выиграй лот на аукционе", "auction_wins", 1,
        "+10,000 NHCoin", "coins", 10_000),
    Achievement("auction_win_5", "Аукционный вампир",
        "Выиграй 5 лотов на аукционе", "auction_wins", 5,
        "+30,000 NHCoin + +5% к доходу", "coins_and_income", 30_000,
        parent_id="auction_win_1"),

    # ─── Коллекция ───
    Achievement("all_achievements", "Коллекционер",
        "Собери все достижения (кроме секретных)", "achievements_count", 20,
        "+75,000 NHCoin + +7% к доходу", "coins_and_income_7", 75_000),
    Achievement("absolute", "Абсолют",
        "Собери все достижения включая секретные", "achievements_count_all", 25,
        "+200,000 NHCoin + +15% к доходу", "coins_and_income_15", 200_000,
        parent_id="all_achievements"),

    # ─── Секретные ───
    Achievement("settings_100", "Параноик",
        "Открой настройки 100 раз", "settings_opened", 100,
        "+1,000 NHCoin", "coins", 1_000, secret=True),
    Achievement("settings_500", "Шизофрения лукизма",
        "Открой настройки 500 раз", "settings_opened", 500,
        "+5,000 NHCoin + +2% к доходу", "coins_and_income_2", 5_000,
        secret=True, parent_id="settings_100"),

    # ─── Квесты ───
    Achievement("future_masterpiece", "Будущий шедевр",
        "Выполни 3 из 5 заданий квеста", "quest_masterpiece", 3,
        "+5,000 NHCoin + +3% к доходу + случайный персонаж", "quest_reward", 5_000),
    Achievement("shadow_syndicate", "Синдикат теней",
        "Получи 3 уникальных персонажа", "unique_chars", 3,
        "+20,000 NHCoin + +7% к доходу", "coins_and_income_7", 20_000,
        parent_id="future_masterpiece"),
]

ACHIEVEMENT_MAP: dict[str, Achievement] = {a.achievement_id: a for a in ACHIEVEMENTS}


@dataclass(frozen=True)
class DonatTitle:
    title_id: str
    name: str
    set_id: str
    description: str
    bonus_description: str
    price_rub: int
    emoji: str


@dataclass(frozen=True)
class DonatSet:
    set_id: str
    name: str
    set_bonus: str
    price_rub: int


DONAT_SETS: list[DonatSet] = [
    DonatSet("strongest_0gen", "Сильнейший 0 поколения",
        "Влияние +100%, +5% шанс тикета, 2 прокрутки тикета подряд", 750),
    DonatSet("genius_maker", "Создатель гениев",
        "Увеличение всех баффов гениев на 20%", 1050),
    DonatSet("monster", "Монстр",
        "Боевая мощь +100%, атака 2 раза подряд, шанс сильнейшей карточки ×5", 1200),
    DonatSet("flow", "Поток",
        "Уменьшение всех КД ещё на 15%", 500),
    DonatSet("ui_set", "UI",
        "Авто-вербовка, авто-тренировка, авто-тикеты, авто-прокрутка, +3 макс тикета", 1000),
]

DONAT_SET_MAP: dict[str, DonatSet] = {s.set_id: s for s in DONAT_SETS}

DONAT_TITLES: list[DonatTitle] = [
    # Сильнейший 0 поколения
    DonatTitle("fist_power",      "Кулак",        "strongest_0gen", "Боевая мощь +20%",                    "+20% боевая мощь",              350, "👊"),
    DonatTitle("romantic_recruit","Романтик",     "strongest_0gen", "Количество вербовки +100%",            "+100% вербовка",                350, "💖"),
    DonatTitle("great_influence", "Великий",      "strongest_0gen", "Влияние не падает ниже 100",           "Мин. влияние = 100",            100, "🛡"),
    # Создатель гениев
    DonatTitle("genius_training", "Гений тренировок",        "genius_maker", "Тренировки +70%",             "+70% тренировки",    50,  "🏋️"),
    DonatTitle("genius_business", "Гений бизнеса",           "genius_maker", "Доход +50%",                  "+50% доход",         100, "💼"),
    DonatTitle("genius_weapon",   "Гений оружия",            "genius_maker", "Боевая мощь +15%",            "+15% боевая мощь",   150, "🔫"),
    DonatTitle("genius_combat",   "Гений боёв",              "genius_maker", "Навыки пути +20%",            "+20% навыки",        100, "⚔️"),
    DonatTitle("genius_hacking",  "Гений хакинга",           "genius_maker", "Вербовка +30%",               "+30% вербовка",      80,  "💻"),
    DonatTitle("genius_medicine", "Гений медицины",          "genius_maker", "Способности пути ×1.30",      "+30% способности",   100, "🩺"),
    DonatTitle("genius_scale",    "Гений масштабирования",   "genius_maker", "Тренировки/доход/вербовка +15%","+15% всё",         200, "📈"),
    DonatTitle("legend_1gen",     "Легенда первого поколения","genius_maker","Крит удар ×3 (шанс 2%)",      "Крит ×3",            250, "👑"),
    # Монстр
    DonatTitle("monster_training","Гений тренировок (Монстр)","monster",     "Тренировки +100%",            "+100% тренировки",   150, "🏋️"),
    DonatTitle("reverse_eyes",    "Обратные глаза",          "monster",      "КД атаки -30%",               "-30% КД атаки",      300, "👁"),
    DonatTitle("selection",       "Отбор",                   "monster",      "+шанс сильных статистов",     "+шанс статистов",    350, "🎯"),
    DonatTitle("manager_fav",     "Любимый перс менеджера",  "monster",      "Шанс тикетов +10%",           "+10% тикет",         400, "💎"),
    # Поток
    DonatTitle("concentration",   "Концентрация",            "flow",         "КД атаки -30%",               "-30% КД атаки",      300, "🎯"),
    DonatTitle("focus",           "Фокус",                   "flow",         "КД вербовки/тренировки -20%", "-20% КД",            200, "🧘"),
    # UI
    DonatTitle("ui_title",        "UI",                      "ui_set",       "Полная автоматизация + +3 тикета","Авто + +3 тикета",1000, "🤖"),
]

DONAT_TITLE_MAP: dict[str, DonatTitle] = {t.title_id: t for t in DONAT_TITLES}

MANAGER_USERNAME = "@JDebobA"