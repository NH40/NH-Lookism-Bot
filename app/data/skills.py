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
        PathSkill("biz_income_1",   "Деловая хватка",      "📈", "+10% к доходу — деньги сами идут в руки",                   "businessman", 3,  {"income_bonus_percent": 10},      0),
        PathSkill("biz_discount_1", "Экономия",            "💸", "-10% стоимость зданий — умеешь торговаться",                "businessman", 4,  {"building_discount_percent": 10}, 0),
        # Уровень 1
        PathSkill("biz_income_2",   "Масштабирование",     "📊", "+20% к доходу — бизнес растёт как на дрожжах",              "businessman", 5,  {"income_bonus_percent": 20},      1),
        PathSkill("biz_quality_1",  "Инвестор в кадры",    "🎓", "+5% к качеству тренировки — вкладываешь в лучших",          "businessman", 5,  {"train_quality_bonus": 5},        1),
        PathSkill("biz_discount_2", "Оптовик",             "🏭", "-20% стоимость зданий — оптом всегда дешевле",              "businessman", 7,  {"building_discount_percent": 20}, 1),
        # Уровень 2
        PathSkill("biz_income_3",   "Монополия",           "🏰", "+30% к доходу — конкурентов не осталось",                   "businessman", 8,  {"income_bonus_percent": 30},      2),
        PathSkill("biz_quality_2",  "Элитный тренер",      "🏆", "+10% к качеству тренировки — только топ бойцы",             "businessman", 9,  {"train_quality_bonus": 10},       2),
        PathSkill("biz_recruit_1",  "HR-директор",         "🤝", "+15% вербовка — кадры решают всё",                          "businessman", 8,  {"recruit_count_bonus": 15},       2),
        # Уровень 3
        PathSkill("biz_multiplier", "Районный барон",      "🌍", "×1.5 к доходу районов — твой район, твои правила",          "businessman", 12, {"district_multiplier": 1.5},      3),
        PathSkill("biz_income_4",   "Корпорация",          "🏙", "+40% к доходу — ты уже не просто бизнесмен",                "businessman", 11, {"income_bonus_percent": 40},      3),
        # Уровень 4
        PathSkill("biz_reket",      "Рэкет",               "🔫", "+1 доп. атака в КД — бизнес надо защищать... кулаками",    "businessman", 14, {"extra_attack_count": 1},         4),
        PathSkill("biz_compound",   "Сложный процент",     "💹", "+50% доход от районов — деньги делают деньги",              "businessman", 13, {"district_multiplier": 1.5},      4),
    ],
    "romantic": [
        # Уровень 0 — базовые
        PathSkill("rom_tickets_1",  "Обаяние",             "💘", "+1 слот тикета — люди тянутся к тебе сами",                "romantic", 3,  {"max_tickets": 1},           0),
        PathSkill("rom_chance_1",   "Везунчик",            "🍀", "+5% шанс тикета — удача любит тебя",                       "romantic", 3,  {"ticket_chance": 5},          0),
        PathSkill("rom_recruit_1",  "Вербовщик",           "👥", "+20% бойцов при вербовке — умеешь убеждать",               "romantic", 4,  {"recruit_count_bonus": 20},   0),
        # Уровень 1
        PathSkill("rom_tickets_2",  "Харизма",             "💝", "+2 слота тикета — твоя улыбка открывает двери",            "romantic", 6,  {"max_tickets": 2},            1),
        PathSkill("rom_chance_2",   "Любимчик судьбы",     "⭐", "+10% шанс тикета — судьба благосклонна к романтикам",     "romantic", 5,  {"ticket_chance": 10},         1),
        PathSkill("rom_quality_1",  "Вдохновение",         "✨", "+5% к качеству тренировки — романтика мотивирует бойцов",  "romantic", 5,  {"train_quality_bonus": 5},    1),
        # Уровень 2
        PathSkill("rom_recruit_2",  "Мастер вербовки",     "🎯", "+40% бойцов — за тобой идут толпами",                     "romantic", 8,  {"recruit_count_bonus": 40},   2),
        PathSkill("rom_chance_3",   "Дитя удачи",          "🌟", "+15% шанс тикета — ты рождён под счастливой звездой",     "romantic", 8,  {"ticket_chance": 15},         2),
        PathSkill("rom_income_1",   "Щедрый покровитель",  "🌹", "+15% доход — любовь окупается",                            "romantic", 7,  {"income_bonus_percent": 15},  2),
        # Уровень 3
        PathSkill("rom_tickets_3",  "Легенда романтики",   "💖", "+3 слота тикета — о тебе слагают легенды",                "romantic", 10, {"max_tickets": 3},            3),
        PathSkill("rom_attack_x",   "Счастливый удар",     "🎲", "+1 доп. атака — удача улыбается смелым",                   "romantic", 13, {"extra_attack_count": 1},     3),
        PathSkill("rom_discount_1", "Народная любовь",     "❤️", "-15% стоимость вербовки — люди идут бесплатно",            "romantic", 11, {"recruit_discount_percent": 15}, 3),
        # Уровень 4
        PathSkill("rom_double",     "Двойная вербовка",    "⚡", "Двойная вербовка — два отряда за один раз",                "romantic", 15, {"double_recruit": True},      4),
        PathSkill("rom_max_ticket", "Звезда удачи",        "🌠", "+1 макс. слот тикета — судьба всегда за тебя",             "romantic", 14, {"max_tickets": 1},            4),
    ],
    "monster": [
        # Уровень 0 — базовые
        PathSkill("mon_train_1",  "Тренировочный монстр", "🏋", "+10% охват тренировки — ты не устаёшь",                    "monster", 3,  {"train_bonus_percent": 10},  0),
        PathSkill("mon_power_1",  "Монстр силы",          "💥", "+10% боевая мощь — твоя банда страшнее всех",               "monster", 5,  {"squad_power_bonus": 10},    0),
        # Уровень 1
        PathSkill("mon_train_2",  "Машина войны",         "⚙️", "+20% охват — твой режим тренировок убивает слабых",         "monster", 6,  {"train_bonus_percent": 20},  1),
        PathSkill("mon_quality_1","Жёсткий тренер",       "🎯", "+10% к качеству тренировки — только жёсткие методы",       "monster", 6,  {"train_quality_bonus": 10},  1),
        PathSkill("mon_ticket_1", "Проверка боем",        "🎟", "+5% шанс тикета — только сильных замечает судьба",          "monster", 5,  {"ticket_chance": 5},         1),
        # Уровень 2
        PathSkill("mon_train_3",  "Абсолютная форма",     "🔥", "+30% охват — ты — живое воплощение силы",                   "monster", 10, {"train_bonus_percent": 30},  2),
        PathSkill("mon_power_2",  "Пиковая форма",        "🌋", "+20% боевая мощь — предел человеческих возможностей",       "monster", 10, {"squad_power_bonus": 20},    2),
        PathSkill("mon_quality_2","Совершенная методика", "🧬", "+15% к качеству тренировки — ты знаешь предел каждого",    "monster", 11, {"train_quality_bonus": 15},  2),
        # Уровень 3
        PathSkill("mon_dtrain",   "Двойная тренировка",   "🔄", "Тренировка 2 раза в КД — отдых для слабаков",              "monster", 12, {"double_train": True},       3),
        PathSkill("mon_extra_atk","Берсерк",              "😤", "+1 доп. атака — ты не останавливаешься, пока враг дышит",  "monster", 14, {"extra_attack_count": 1},    3),
        PathSkill("mon_power_3",  "Непоколебимый",        "🗿", "+30% боевая мощь — тебя уже боятся все вокруг",             "monster", 13, {"squad_power_bonus": 30},    3),
        # Уровень 4
        PathSkill("mon_dattack",  "Двойная атака",        "⚔️", "Атака 2 раза в КД — бей пока стоишь",                      "monster", 15, {"double_attack": True},      4),
        PathSkill("mon_fury",     "Ярость монстра",       "😱", "+1 доп. атака + серия побед усиливает следующий удар",      "monster", 14, {"extra_attack_count": 1},    4),
    ],
    "shadow": [
        # ── Тень: путь скрытности, скорости и манипуляций ─────────────────────
        # Уровень 0
        PathSkill("shd_cd_1",     "Бесшумный шаг",     "🌑", "-10% КД всех действий — ты двигаешься незаметно",        "shadow", 3,  {"all_cd_reduction": 10},         0),
        PathSkill("shd_power_1",  "Удар из тени",       "🗡",  "+7% боевая мощь — первый удар всегда неожиданный",      "shadow", 4,  {"squad_power_bonus": 7},         0),
        # Уровень 1
        PathSkill("shd_ticket_1", "Случайная удача",    "🎲", "+3% шанс тикета — хаос работает в твою пользу",          "shadow", 5,  {"ticket_chance": 3},             1),
        PathSkill("shd_cd_2",     "Теневая скорость",   "⚡", "-15% КД атаки — ты быстрее чем кажешься",                "shadow", 6,  {"all_cd_reduction": 15},         1),
        # Уровень 2
        PathSkill("shd_power_2",  "Ночной охотник",     "🌙", "+15% боевая мощь — в темноте ты непобедим",              "shadow", 8,  {"squad_power_bonus": 15},        2),
        PathSkill("shd_income_1", "Теневой рэкет",      "💸", "+10% доход — нелегальный бизнес всегда доходнее",        "shadow", 7,  {"income_bonus_percent": 10},     2),
        # Уровень 3
        PathSkill("shd_first_atk","Первый удар",        "💥", "Первая атака в бою +10% мощи — бей первым, бей жёстко",  "shadow", 10, {"path_unique_1": True},          3),
        PathSkill("shd_cd_3",     "Поток теней",        "🌊", "-10% ещё КД всего — скорость твой конёк",               "shadow", 11, {"all_cd_reduction": 10},         3),
        # Уровень 4
        PathSkill("shd_invisible","Скрытность",         "🫥", "Скрыть себя в топе — никто не знает чего ты достиг",    "shadow", 14, {"path_unique_2": True},          4),
        PathSkill("shd_streak",   "Серийный убийца",    "🔪", "+1 доп. атака — добивай пока враг не успел опомниться", "shadow", 15, {"extra_attack_count": 1},        4),
    ],
}

# Синергии путей: (основной_путь, путь_слитого_навыка) → бонус
# Активируется однократно при получении первого навыка чужого пути
PATH_SYNERGIES: dict[tuple[str, str], dict] = {
    # Существующие синергии
    ("businessman", "monster"):   {"name": "Беспощадный капиталист",  "emoji": "💰", "effect": {"income_bonus_percent": 5},      "desc": "+5% доход — бизнес с кулаком"},
    ("businessman", "romantic"):  {"name": "Харизматичный делец",     "emoji": "🤝", "effect": {"recruit_discount_percent": 15}, "desc": "-15% стоимость вербовки"},
    ("businessman", "shadow"):    {"name": "Теневой капитал",         "emoji": "🌑", "effect": {"income_bonus_percent": 10},     "desc": "+10% доход — деньги не пахнут"},
    ("romantic",    "monster"):   {"name": "Страсть к власти",        "emoji": "🔥", "effect": {"train_bonus_percent": 10},     "desc": "+10% охват тренировки"},
    ("romantic",    "businessman"):{"name": "Богатый покровитель",    "emoji": "💝", "effect": {"ticket_chance": 5},            "desc": "+5% шанс тикета"},
    ("romantic",    "shadow"):    {"name": "Роковое влечение",        "emoji": "🌹", "effect": {"ticket_chance": 5},            "desc": "+5% шанс тикета — опасная привлекательность"},
    ("monster",     "businessman"):{"name": "Рэкетир",                "emoji": "😤", "effect": {"income_bonus_percent": 5},     "desc": "+5% доход"},
    ("monster",     "romantic"):  {"name": "Одержимость силой",       "emoji": "👹", "effect": {"train_bonus_percent": 5},      "desc": "+5% охват тренировки"},
    ("monster",     "shadow"):    {"name": "Ночная ярость",           "emoji": "🌑", "effect": {"squad_power_bonus": 7},        "desc": "+7% боевая мощь — удвоенная жестокость"},
    ("shadow",      "businessman"):{"name": "Серый кардинал",         "emoji": "🃏", "effect": {"income_bonus_percent": 5},     "desc": "+5% доход — управляй из тени"},
    ("shadow",      "romantic"):  {"name": "Теневой обаятель",        "emoji": "💫", "effect": {"recruit_count_bonus": 12},     "desc": "+12% вербовка — умеешь убеждать незаметно"},
    ("shadow",      "monster"):   {"name": "Призрак войны",           "emoji": "⚔️", "effect": {"squad_power_bonus": 8},        "desc": "+8% боевая мощь — быстрый и смертоносный"},
}