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
    Achievement("power_500k", "Полмиллиона — серьёзный разговор",
        "Набери 500,000 боевой мощи", "combat_power", 500_000,
        "+25,000 NHCoin + +5% к доходу", "coins_and_income", 25_000,
        parent_id="power_100k"),
    Achievement("power_1m", "Ну ты мощный",
        "Набери 1,000,000 боевой мощи", "combat_power", 1_000_000,
        "+50,000 NHCoin + +10% к доходу", "coins_and_income_10", 50_000,
        parent_id="power_500k"),

    # ─── Фазы ───
    Achievement("first_king", "Король лужи — тоже король",
        "Стань Королём", "phase_reached", 1,
        "+7,000 NHCoin + +5% к доходу", "coins_and_income", 7_000),
    Achievement("king_5_cities", "Половина пути",
        "Захвати 5 городов в фазе Короля", "king_cities_count", 5,
        "+5,000 NHCoin", "coins", 5_000, parent_id="first_king"),
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

    # ─── Престиж ───
    Achievement("prestige_1", "Первое пробуждение",
        "Достигни первого уровня пробуждения", "prestige_level", 1,
        "+3 очка пути", "path_points", 3),
    Achievement("prestige_3", "Трижды рождённый",
        "Достигни третьего уровня пробуждения", "prestige_level", 3,
        "+30,000 NHCoin + +5% к доходу", "coins_and_income", 30_000,
        parent_id="prestige_1"),

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
    Achievement("spend_5m", "Щедрый спонсор",
        "Потрать 5,000,000 NHCoin", "coins_spent", 5_000_000,
        "+50,000 NHCoin + +7% к доходу", "coins_and_income_7", 50_000,
        parent_id="spend_1m"),

    # ─── Бои ───
    Achievement("wins_10", "Вроде неплох, но лох",
        "Выиграй 10 боёв", "total_wins", 10,
        "+300 NHCoin", "coins", 300),
    Achievement("wins_100", "Вроде лох, но ты неплох",
        "Выиграй 100 боёв", "total_wins", 100,
        "+5,000 NHCoin + +3% к доходу", "coins_and_income_3", 5_000,
        parent_id="wins_10"),
    Achievement("wins_500", "Легенда ринга",
        "Выиграй 500 боёв", "total_wins", 500,
        "+20,000 NHCoin + +3% к доходу", "coins_and_income_3", 20_000,
        parent_id="wins_100"),
    Achievement("wins_1000", "Непобедимый",
        "Выиграй 1,000 боёв", "total_wins", 1000,
        "+75,000 NHCoin + +7% к доходу", "coins_and_income_7", 75_000,
        parent_id="wins_500"),

    # ─── Аукцион ───
    Achievement("auction_win_1", "Денег куры не клюют",
        "Выиграй лот на аукционе", "auction_wins", 1,
        "+10,000 NHCoin", "coins", 10_000),
    Achievement("auction_win_5", "Аукционный вампир",
        "Выиграй 5 лотов на аукционе", "auction_wins", 5,
        "+30,000 NHCoin + +5% к доходу", "coins_and_income", 30_000,
        parent_id="auction_win_1"),

    # ─── Рейды ───
    Achievement("raid_boss_1", "Первая кровь",
        "Победи рейд-босса 1 раз", "raid_boss_wins", 1,
        "+3,000 NHCoin", "coins", 3_000),
    Achievement("raid_boss_10", "Охотник на боссов",
        "Победи рейд-боссов 10 раз", "raid_boss_wins", 10,
        "+15,000 NHCoin + +3% к доходу", "coins_and_income_3", 15_000,
        parent_id="raid_boss_1"),
    Achievement("raid_boss_100", "Легенда рейдов",
        "Победи рейд-боссов 100 раз", "raid_boss_wins", 100,
        "+75,000 NHCoin + +7% к доходу", "coins_and_income_7", 75_000,
        parent_id="raid_boss_10"),

    # ─── Армия ───
    Achievement("army_100k", "Полководец",
        "Завербуй 100,000 статистов за всё время", "total_statists_recruited", 100_000,
        "+20,000 NHCoin + +5% к доходу", "coins_and_income", 20_000),
    Achievement("army_1m", "Империя теней",
        "Завербуй 1,000,000 статистов за всё время", "total_statists_recruited", 1_000_000,
        "+100,000 NHCoin + +10% к доходу", "coins_and_income_10", 100_000,
        parent_id="army_100k"),

    # ─── Путь / УИ / Гений медицины ───
    Achievement("path_max", "Дорога познана",
        "Улучши путь до максимального уровня (5)", "skill_path_level", 5,
        "+10,000 NHCoin + +5% к доходу", "coins_and_income", 10_000),
    Achievement("ui_master", "Мастер инстинкта",
        "Достигни максимального уровня Ультра Инстинкта (4)", "ui_level_max", 4,
        "+20,000 NHCoin + +5% к доходу", "coins_and_income", 20_000),
    Achievement("med_genius_master", "Гений медицины (мастер)",
        "Открой все зелья Гения Медицины до ур. 5+", "med_genius_max", 5,
        "+20,000 NHCoin + +5% к доходу", "coins_and_income", 20_000),

    # ─── Коллекция персонажей ───
    Achievement("collect_rank_complete", "Архивариус",
        "Собери всех персонажей одной редкости (хотя бы по одному каждого)", "any_rank_complete", 1,
        "+15,000 NHCoin + +5% к доходу", "coins_and_income", 15_000),

    # ─── Ежедневные задания ───
    Achievement("quests_100", "Ответственный",
        "Выполни 100 ежедневных заданий", "daily_quests_completed", 100,
        "+8,000 NHCoin + +3% к доходу", "coins_and_income_3", 8_000),
    Achievement("quests_500", "Дисциплинированный",
        "Выполни 500 ежедневных заданий", "daily_quests_completed", 500,
        "+30,000 NHCoin + +5% к доходу", "coins_and_income", 30_000,
        parent_id="quests_100"),
    Achievement("quests_1000", "Человек-машина",
        "Выполни 1,000 ежедневных заданий", "daily_quests_completed", 1_000,
        "+100,000 NHCoin + +7% к доходу", "coins_and_income_7", 100_000,
        parent_id="quests_500"),

    # ─── Биржа ───
    Achievement("market_10", "Торговец",
        "Продай товар на бирже 10 раз", "market_sells", 10,
        "+10,000 NHCoin + +3% к доходу", "coins_and_income_3", 10_000),
    Achievement("market_100", "Барыга",
        "Продай товар на бирже 100 раз", "market_sells", 100,
        "+50,000 NHCoin + +7% к доходу", "coins_and_income_7", 50_000,
        parent_id="market_10"),

    # ─── Особые ───
    Achievement("future_masterpiece", "Будущий шедевр",
        "Накопи 100 очков мастерства (от Тома Ли)", "mastery_points", 100,
        "+5,000 NHCoin + +3% к доходу + случайный персонаж", "quest_reward", 5_000),
    Achievement("shadow_syndicate", "Синдикат теней",
        "Получи 3 уникальных персонажа", "unique_chars", 3,
        "+20,000 NHCoin + +7% к доходу", "coins_and_income_7", 20_000,
        parent_id="future_masterpiece"),

    # ─── Коллекция ───
    # Несекретных без self: 26 старых + 14 новых = 40
    Achievement("all_achievements", "Коллекционер",
        "Собери все несекретные достижения", "achievements_count", 40,
        "+75,000 NHCoin + +7% к доходу", "coins_and_income_7", 75_000),
    # Все (40 несекрет + 2 секрет + 1 all_achievements) = 43
    Achievement("absolute", "Абсолют",
        "Собери абсолютно все достижения", "achievements_count_all", 43,
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
        "Влияние +60%, +5% шанс тикета, 2 прокрутки тикета подряд, +2 доп. слота на каждый путь, макс. тикет 90%", 1700),
    DonatSet("genius_maker", "Создатель гениев",
        "Увеличение всех баффов гениев на 20%", 1150),
    DonatSet("monster", "Монстр",
        "Боевая мощь +60%, атака 2 раза подряд, шанс сильнейшей карточки ×5", 1200),
    DonatSet("flow", "Поток",
        "Уменьшение всех КД ещё на 15%", 1600),
    DonatSet("ui_set", "UI",
        "Авто-вербовка, авто-тренировка, авто-тикеты, авто-прокрутка, Гений медицины (макс), +3 макс тикета", 1500),
]

DONAT_SET_MAP: dict[str, DonatSet] = {s.set_id: s for s in DONAT_SETS}

DONAT_TITLES: list[DonatTitle] = [
    # Сильнейший 0 поколения
    DonatTitle("fist_power",      "Кулак",        "strongest_0gen", "Боевая мощь +20%",                    "+20% боевая мощь",              350, "👊"),
    DonatTitle("romantic_recruit","Романтик",     "strongest_0gen", "Количество вербовки +40%",            "+40% вербовка",                 350, "💖"),
    DonatTitle("great_influence", "Великий",      "strongest_0gen", "Влияние не падает ниже 3000",          "Мин. влияние = 3000",           100, "🛡"),

    # Создатель гениев
    DonatTitle("genius_training", "Гений тренировок",        "genius_maker", "Тренировки +70%",             "+70% тренировки",    50,  "🏋️"),
    DonatTitle("genius_business", "Гений бизнеса",           "genius_maker", "Доход +50%",                  "+50% доход",         200, "💼"),
    DonatTitle("genius_weapon",   "Гений оружия",            "genius_maker", "Боевая мощь +15%",            "+15% боевая мощь",   150, "🔫"),
    DonatTitle("genius_combat",   "Гений боёв",              "genius_maker", "Навыки пути +20%",            "+20% навыки",        100, "⚔️"),
    DonatTitle("genius_hacking",  "Гений хакинга",           "genius_maker", "Вербовка +30%",               "+30% вербовка",      80,  "💻"),
    DonatTitle("genius_medicine", "Гений медицины",          "genius_maker", "Способности пути ×1.30",      "+30% способности",   100, "🩺"),
    DonatTitle("genius_scale",    "Гений масштабирования",   "genius_maker", "Тренировки/доход/вербовка +15%","+15% всё",         200, "📈"),
    DonatTitle("legend_1gen",     "Легенда первого поколения","genius_maker","Крит удар ×3 (шанс 2%)",      "Крит ×3",            250, "👑"),

    # Монстр
    DonatTitle("monster_training","Гений тренировок (Монстр)","monster",     "Тренировки +100%",            "+100% тренировки",   150, "🏋️"),
    DonatTitle("reverse_eyes",    "Обратные глаза",          "monster",      "КД атаки -25%",               "-25% КД атаки",      300, "👁"),
    DonatTitle("selection",       "Отбор",                   "monster",      "+шанс сильных статистов",     "+шанс статистов",    350, "🎯"),
    DonatTitle("manager_fav",     "Любимый перс менеджера",  "monster",      "Шанс тикетов +5%",            "+5% тикет",          400, "💎"),

    # Поток
    DonatTitle("concentration",   "Концентрация",            "flow",         "КД всего -10%",               "-10% все КД",        300, "🎯"),
    DonatTitle("focus",           "Фокус",                   "flow",         "КД всего -20%",               "-20% все КД",        200, "🧘"),
    DonatTitle("raid_cd",         "Рейдовый ускоритель",     "flow",         "КД всего -20%",               "-20% все КД",        600, "⏱️"),
    DonatTitle("duel_cd",         "Карточный мастер",        "flow",         "КД дуэлей карточек -20%",     "-20% КД дуэлей",     500, "🃏"),

    # UI
    DonatTitle("ui_title",        "UI",                      "ui_set",       "Полная автоматизация + +3 тикета","Авто + +3 тикета",1000, "🤖"),
    DonatTitle("ui_potion",       "Гений медицины (Фулл)",   "ui_set",       "Все авто-зелья навсегда — Гений медицины макс. уровень (все 6 зелий, ур.6)", "МГ макс. уровень", 500, "🩺"),

    # Сильнейший 0 поколения — расширение
    DonatTitle("rom_extra_skills", "Три пути",               "strongest_0gen", "+2 доп. слота на каждый путь — навыки всех путей доступны (покупка за 5× цену)", "+2 слота на путь", 500, "🌐"),
    DonatTitle("rom_max_chance",   "Фавор судьбы",           "strongest_0gen", "Максимальный шанс тикета 90%",   "Макс. тикет 90%",  400,  "🍀"),
]

DONAT_TITLE_MAP: dict[str, DonatTitle] = {t.title_id: t for t in DONAT_TITLES}


# ── Круговые донаты (Black Market) ──────────────────────────────────────────

@dataclass(frozen=True)
class CircularDonat:
    donat_id: str
    name: str
    emoji: str
    price_per_circle: int
    max_circles: int
    circle_bonus: str              # бонус за каждый оплаченный круг
    special_bonuses: tuple         # ((circle_n, description), ...)


CIRCULAR_DONATS: list[CircularDonat] = [
    CircularDonat(
        "archangel", "Архангел", "👼",
        price_per_circle=1000, max_circles=10,
        circle_bonus="Боевая сила +30%, доход +50%, пассивный доход 500 NHCoin/час",
        special_bonuses=(
            (3,  "+10% к урону в рейдах"),
            (5,  "Отражает 3% урона при атаке по вам"),
            (10, "1 раз в день выдаётся 64 района"),
        ),
    ),
    CircularDonat(
        "clan_head", "Глава клана", "👑",
        price_per_circle=1000, max_circles=5,
        circle_bonus="Все члены клана +5% к силе, доходу, вербовке, влиянию. Лично: +10% сила, +5% влияние",
        special_bonuses=(
            (5, "При пополнении казны: шанс 3% вернуть от 5% до 10% кешбека"),
        ),
    ),
    CircularDonat(
        "korea_devil", "Дьявол из Кореи", "👹",
        price_per_circle=1200, max_circles=6,
        circle_bonus="Боевая сила +10%, влияние +10%, пассивный доход 300 NHCoin/час",
        special_bonuses=(
            (3, "Шанс 5%: мгновенно завершить рейд"),
            (6, "Шанс 5%: награда за рейд удвоена"),
        ),
    ),
    CircularDonat(
        "mountain_lord", "Хозяин горы", "⛰️",
        price_per_circle=1200, max_circles=4,
        circle_bonus="Боевая сила +20%, влияние +10%",
        special_bonuses=(
            (2, "+2/4/6/8/12 районов при захвате города (зависит от размера)"),
            (4, "Можно превысить лимит тикетов на 100%"),
        ),
    ),
    CircularDonat(
        "shadow", "Тень", "🌑",
        price_per_circle=1200, max_circles=5,
        circle_bonus="-1% ко всем КД за каждый круг",
        special_bonuses=(
            (3, "Первая атака в бою +10% боевой мощи"),
            (5, "Можно скрыть себя в топе игроков"),
        ),
    ),
    CircularDonat(
        "dragon", "Дракон", "🐉",
        price_per_circle=1200, max_circles=6,
        circle_bonus="Боевая сила +10%",
        special_bonuses=(
            (3, "+10% к защите (урон по вам уменьшается на 10%)"),
            (6, "Спутник-дракон: +15% ко всем характеристикам в рейде на 1 час"),
        ),
    ),
    CircularDonat(
        "dungeon_lord", "Хозяин подземелий", "🏚️",
        price_per_circle=800, max_circles=4,
        circle_bonus="Пассивный доход 1000 NHCoin/час, +5% ко всем фрагментам, +5% шанс тренировки",
        special_bonuses=(
            (2, "+10% ко всем фрагментам"),
            (4, "+10% ко всем фрагментам (итого +25%)"),
        ),
    ),
    CircularDonat(
        "emperor_circle", "Император", "🏛",
        price_per_circle=1200, max_circles=10,
        circle_bonus="Боевая сила +20%, влияние +10%, пассивный доход 400 NHCoin/час, вербовка +30%, стоимость у Тома Ли и Чон Гона -2%",
        special_bonuses=(
            (3,  "+5% ко всем следующим баффам этого доната"),
            (5,  "+5% ко всем следующим баффам этого доната"),
            (10, "+5% ко всем баффам этого доната"),
        ),
    ),
]

CIRCULAR_DONAT_MAP: dict[str, CircularDonat] = {d.donat_id: d for d in CIRCULAR_DONATS}


# ── Клановые донаты ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClanDonatItem:
    item_id: str
    name: str
    emoji: str
    description: str
    price_rub: int


CLAN_DONAT_ITEMS: list[ClanDonatItem] = [
    ClanDonatItem("clan_wealth",  "Богатство клана",  "💰", "+10% доход всем участникам клана",                     500),
    ClanDonatItem("clan_luck",    "Удача клана",       "🍀", "+5% шанс тикета всем участникам",                      400),
    ClanDonatItem("clan_school",  "Школа клана",       "🏋️", "+10% охват тренировки всем участникам",                350),
    ClanDonatItem("clan_war",     "Клан Войн",         "⚔️", "+10% доход + +10% тренировки всем",                    900),
    ClanDonatItem("clan_premium", "Премиум клан",      "👑", "+15% доход + +5% шанс тикета + +10% тренировки всем", 1500),
]

CLAN_DONAT_ITEM_MAP: dict[str, ClanDonatItem] = {c.item_id: c for c in CLAN_DONAT_ITEMS}

MANAGER_USERNAME = "@JDebobA"