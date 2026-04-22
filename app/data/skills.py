from dataclasses import dataclass

@dataclass
class MasteryLevelConfig:
    level: int
    bonus: int     # %
    cost: int      # NHCoin

@dataclass
class MasteryConfig:
    skill_id: str
    name: str
    emoji: str
    description: str
    effect_field: str   # поле в User которое меняется
    levels: list[MasteryLevelConfig]

@dataclass
class PathSkill:
    skill_id: str
    name: str
    emoji: str
    description: str
    path: str
    cost: int           # очки пути
    effect: dict        # {"field": "value"}

MASTERY: list[MasteryConfig] = [
    MasteryConfig(
        "strength", "Сила", "💪",
        "Боевая мощь отряда", "squad_power_bonus",
        [
            MasteryLevelConfig(0, 0,   0),
            MasteryLevelConfig(1, 5,   2000),
            MasteryLevelConfig(2, 10,  6000),
            MasteryLevelConfig(3, 20,  15000),
            MasteryLevelConfig(4, 30,  40000),
        ]
    ),
    MasteryConfig(
        "speed", "Скорость", "⚡",
        "Сокращение ВСЕХ КД (атака, вербовка, тренировка, тикет)", "all_cd_reduction",
        [
            MasteryLevelConfig(0, 0,  0),
            MasteryLevelConfig(1, 5,  2000),
            MasteryLevelConfig(2, 10, 6000),
            MasteryLevelConfig(3, 15, 15000),
            MasteryLevelConfig(4, 20, 40000),
        ]
    ),
    MasteryConfig(
        "endurance", "Выносливость", "🛡",
        "Победа над врагами сильнее на X%", "endurance_bonus",
        [
            MasteryLevelConfig(0, 0,  0),
            MasteryLevelConfig(1, 5,  2000),
            MasteryLevelConfig(2, 10, 6000),
            MasteryLevelConfig(3, 15, 15000),
            MasteryLevelConfig(4, 20, 40000),
        ]
    ),
    MasteryConfig(
        "technique", "Техника", "🏋",
        "Охват тренировки + доход с бизнеса", "train_and_income",
        [
            MasteryLevelConfig(0, 0,  0),
            MasteryLevelConfig(1, 5,  2000),
            MasteryLevelConfig(2, 10, 6000),
            MasteryLevelConfig(3, 20, 15000),
            MasteryLevelConfig(4, 30, 40000),
        ]
    ),
]

MASTERY_BY_ID: dict[str, MasteryConfig] = {m.skill_id: m for m in MASTERY}

# Пути навыков
PATH_SKILLS: dict[str, list[PathSkill]] = {
    "businessman": [
        PathSkill("biz_income_1",   "Деловая хватка",    "📈", "+10% к доходу",              "businessman", 3,  {"income_bonus_percent": 10}),
        PathSkill("biz_income_2",   "Масштабирование",   "📊", "+20% к доходу (доп.)",        "businessman", 5,  {"income_bonus_percent": 20}),
        PathSkill("biz_income_3",   "Монополия",         "🏰", "+30% к доходу (доп.)",        "businessman", 8,  {"income_bonus_percent": 30}),
        PathSkill("biz_discount_1", "Экономия",          "💸", "-10% стоимость зданий",       "businessman", 4,  {"building_discount_percent": 10}),
        PathSkill("biz_discount_2", "Оптовик",           "🏭", "-20% стоимость зданий (доп.)","businessman", 7,  {"building_discount_percent": 20}),
        PathSkill("biz_multiplier", "Районный барон",    "🌍", "×1.5 к доходу районов",       "businessman", 12, {"district_multiplier": 1.5}),
    ],
    "romantic": [
        PathSkill("rom_tickets_1",  "Обаяние",           "💘", "+1 слот тикета",              "romantic", 3,  {"max_tickets": 1}),
        PathSkill("rom_tickets_2",  "Харизма",           "💝", "+2 слота тикета (доп.)",      "romantic", 6,  {"max_tickets": 2}),
        PathSkill("rom_tickets_3",  "Легенда романтики", "💖", "+3 слота тикета (доп.)",      "romantic", 10, {"max_tickets": 3}),
        PathSkill("rom_chance_1",   "Везунчик",          "🍀", "+5% шанс тикета",             "romantic", 3,  {"ticket_chance": 5}),
        PathSkill("rom_chance_2",   "Любимчик судьбы",   "⭐", "+10% шанс тикета (доп.)",     "romantic", 5,  {"ticket_chance": 10}),
        PathSkill("rom_chance_3",   "Дитя удачи",        "🌟", "+15% шанс тикета (доп.)",     "romantic", 8,  {"ticket_chance": 15}),
        PathSkill("rom_recruit_1",  "Вербовщик",         "👥", "+20% бойцов при вербовке",    "romantic", 4,  {"recruit_count_bonus": 20}),
        PathSkill("rom_recruit_2",  "Мастер вербовки",   "🎯", "+40% бойцов (доп.)",          "romantic", 8,  {"recruit_count_bonus": 40}),
        PathSkill("rom_double",     "Двойная вербовка",  "⚡", "Двойная вербовка",             "romantic", 15, {"double_recruit": True}),
    ],
    "monster": [
        PathSkill("mon_train_1",  "Тренировочный монстр","🏋", "+10% охват тренировки",       "monster", 3,  {"train_bonus_percent": 10}),
        PathSkill("mon_train_2",  "Машина войны",        "⚙️", "+20% охват (доп.)",           "monster", 6,  {"train_bonus_percent": 20}),
        PathSkill("mon_train_3",  "Абсолютная форма",    "🔥", "+30% охват (доп.)",            "monster", 10, {"train_bonus_percent": 30}),
        PathSkill("mon_power_1",  "Монстр силы",         "💥", "+10% боевая мощь",             "monster", 5,  {"squad_power_bonus": 10}),
        PathSkill("mon_power_2",  "Пиковая форма",       "🌋", "+20% боевая мощь (доп.)",      "monster", 10, {"squad_power_bonus": 20}),
        PathSkill("mon_dtrain",   "Двойная тренировка",  "🔄", "Тренировка 2 раза в КД",       "monster", 12, {"double_train": True}),
        PathSkill("mon_dattack",  "Двойная атака",       "⚔️", "Атака 2 раза в КД",            "monster", 15, {"double_attack": True}),
    ],
}