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
    min_path_level: int = 0  # минимальный уровень пути для разблокировки

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
        # Уровень 0 — базовые
        PathSkill("biz_income_1",   "Деловая хватка",      "📈", "+10% к доходу — деньги сами идут в руки",                  "businessman", 3,  {"income_bonus_percent": 10},      0),
        PathSkill("biz_discount_1", "Экономия",            "💸", "-10% стоимость зданий — умеешь торговаться",               "businessman", 4,  {"building_discount_percent": 10}, 0),
        # Уровень 1
        PathSkill("biz_income_2",   "Масштабирование",     "📊", "+20% к доходу — бизнес растёт как на дрожжах",             "businessman", 5,  {"income_bonus_percent": 20},      1),
        PathSkill("biz_quality_1",  "Инвестор в кадры",    "🎓", "+5% к качеству тренировки — вкладываешь в лучших",         "businessman", 5,  {"train_quality_bonus": 5},        1),
        PathSkill("biz_discount_2", "Оптовик",             "🏭", "-20% стоимость зданий — оптом всегда дешевле",             "businessman", 7,  {"building_discount_percent": 20}, 1),
        # Уровень 2
        PathSkill("biz_income_3",   "Монополия",           "🏰", "+30% к доходу — конкурентов не осталось",                  "businessman", 8,  {"income_bonus_percent": 30},      2),
        PathSkill("biz_quality_2",  "Элитный тренер",      "🏆", "+10% к качеству тренировки — только топ бойцы",            "businessman", 9,  {"train_quality_bonus": 10},       2),
        # Уровень 3
        PathSkill("biz_multiplier", "Районный барон",      "🌍", "×1.5 к доходу районов — твой район, твои правила",         "businessman", 12, {"district_multiplier": 1.5},      3),
        # Уровень 4
        PathSkill("biz_reket",      "Рэкет",               "🔫", "+1 доп. атака в КД — бизнес надо защищать... кулаками",   "businessman", 14, {"extra_attack_count": 1},         4),
    ],
    "romantic": [
        # Уровень 0 — базовые
        PathSkill("rom_tickets_1",  "Обаяние",             "💘", "+1 слот тикета — люди тянутся к тебе сами",               "romantic", 3,  {"max_tickets": 1},          0),
        PathSkill("rom_chance_1",   "Везунчик",            "🍀", "+5% шанс тикета — удача любит тебя",                      "romantic", 3,  {"ticket_chance": 5},         0),
        PathSkill("rom_recruit_1",  "Вербовщик",           "👥", "+20% бойцов при вербовке — умеешь убеждать",              "romantic", 4,  {"recruit_count_bonus": 20},  0),
        # Уровень 1
        PathSkill("rom_tickets_2",  "Харизма",             "💝", "+2 слота тикета — твоя улыбка открывает двери",           "romantic", 6,  {"max_tickets": 2},          1),
        PathSkill("rom_chance_2",   "Любимчик судьбы",     "⭐", "+10% шанс тикета — судьба благосклонна к романтикам",    "romantic", 5,  {"ticket_chance": 10},        1),
        PathSkill("rom_quality_1",  "Вдохновение",         "✨", "+5% к качеству тренировки — романтика мотивирует бойцов", "romantic", 5,  {"train_quality_bonus": 5},   1),
        # Уровень 2
        PathSkill("rom_recruit_2",  "Мастер вербовки",     "🎯", "+40% бойцов — за тобой идут толпами",                    "romantic", 8,  {"recruit_count_bonus": 40},  2),
        PathSkill("rom_chance_3",   "Дитя удачи",          "🌟", "+15% шанс тикета — ты рождён под счастливой звездой",    "romantic", 8,  {"ticket_chance": 15},        2),
        # Уровень 3
        PathSkill("rom_tickets_3",  "Легенда романтики",   "💖", "+3 слота тикета — о тебе слагают легенды",               "romantic", 10, {"max_tickets": 3},          3),
        PathSkill("rom_attack_x",   "Счастливый удар",     "🎲", "+1 доп. атака — удача улыбается смелым",                  "romantic", 13, {"extra_attack_count": 1},    3),
        # Уровень 4
        PathSkill("rom_double",     "Двойная вербовка",    "⚡", "Двойная вербовка — два за один раз",                      "romantic", 15, {"double_recruit": True},     4),
    ],
    "monster": [
        # Уровень 0 — базовые
        PathSkill("mon_train_1",  "Тренировочный монстр", "🏋", "+10% охват тренировки — ты не устаёшь",                   "monster", 3,  {"train_bonus_percent": 10},  0),
        PathSkill("mon_power_1",  "Монстр силы",          "💥", "+10% боевая мощь — твоя банда страшнее всех",              "monster", 5,  {"squad_power_bonus": 10},    0),
        # Уровень 1
        PathSkill("mon_train_2",  "Машина войны",         "⚙️", "+20% охват — твой режим тренировок убивает слабых",        "monster", 6,  {"train_bonus_percent": 20},  1),
        PathSkill("mon_quality_1","Жёсткий тренер",       "🎯", "+10% к качеству тренировки — только жёсткие методы",      "monster", 6,  {"train_quality_bonus": 10},  1),
        # Уровень 2
        PathSkill("mon_train_3",  "Абсолютная форма",     "🔥", "+30% охват — ты — живое воплощение силы",                  "monster", 10, {"train_bonus_percent": 30},  2),
        PathSkill("mon_power_2",  "Пиковая форма",        "🌋", "+20% боевая мощь — предел человеческих возможностей",      "monster", 10, {"squad_power_bonus": 20},    2),
        PathSkill("mon_quality_2","Совершенная методика", "🧬", "+15% к качеству тренировки — ты знаешь предел каждого",   "monster", 11, {"train_quality_bonus": 15},  2),
        # Уровень 3
        PathSkill("mon_dtrain",   "Двойная тренировка",   "🔄", "Тренировка 2 раза в КД — отдых — для слабаков",           "monster", 12, {"double_train": True},       3),
        PathSkill("mon_extra_atk","Берсерк",              "😤", "+1 доп. атака — ты не останавливаешься, пока враг дышит", "monster", 14, {"extra_attack_count": 1},    3),
        # Уровень 4
        PathSkill("mon_dattack",  "Двойная атака",        "⚔️", "Атака 2 раза в КД — бей пока стоишь",                     "monster", 15, {"double_attack": True},      4),
    ],
}

# Синергии путей: (основной_путь, путь_слитого_навыка) → бонус
# Активируется однократно при получении первого навыка чужого пути
PATH_SYNERGIES: dict[tuple[str, str], dict] = {
    ("businessman", "monster"):   {"name": "Беспощадный капиталист", "emoji": "💰", "effect": {"income_bonus_percent": 5}},
    ("businessman", "romantic"):  {"name": "Харизматичный делец",    "emoji": "🤝", "effect": {"recruit_discount_percent": 15}},
    ("romantic",    "monster"):   {"name": "Страсть к власти",       "emoji": "🔥", "effect": {"train_bonus_percent": 10}},
    ("romantic",    "businessman"):{"name": "Богатый покровитель",   "emoji": "💝", "effect": {"ticket_chance": 5}},
    ("monster",     "businessman"):{"name": "Рэкетир",               "emoji": "😤", "effect": {"income_bonus_percent": 5}},
    ("monster",     "romantic"):  {"name": "Одержимость силой",      "emoji": "👹", "effect": {"train_bonus_percent": 5}},
}