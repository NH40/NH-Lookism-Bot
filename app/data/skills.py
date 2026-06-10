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
        PathSkill("biz_income_1",   "Деловая хватка",      "📈", "+8% к доходу — деньги сами идут в руки",                    "businessman", 3,  {"income_bonus_percent": 8},       0),
        PathSkill("biz_discount_1", "Экономия",            "💸", "-5% стоимость зданий — умеешь торговаться",                  "businessman", 4,  {"building_discount_percent": 5},  0),
        # Уровень 1
        PathSkill("biz_income_2",   "Масштабирование",     "📊", "+12% к доходу — бизнес растёт как на дрожжах",              "businessman", 5,  {"income_bonus_percent": 12},      1),
        PathSkill("biz_quality_1",  "Земельный банк",      "🏘", "+2 бонусных района — расширяй бизнес без войны",            "businessman", 5,  {"bonus_business_districts": 2},   1),
        PathSkill("biz_discount_2", "Оптовик",             "🏭", "-10% стоимость зданий — оптом всегда дешевле",               "businessman", 7,  {"building_discount_percent": 10}, 1),
        # Уровень 2
        PathSkill("biz_income_3",   "Монополия",           "🏰", "+18% к доходу — конкурентов не осталось",                   "businessman", 8,  {"income_bonus_percent": 18},      2),
        PathSkill("biz_quality_2",  "Мегаэкспансия",       "🌆", "+4 бонусных района — ты скупаешь всё",                      "businessman", 9,  {"bonus_business_districts": 4},   2),
        PathSkill("biz_recruit_1",  "HR-директор",         "🤝", "+8% вербовка — кадры решают всё",                           "businessman", 8,  {"recruit_count_bonus": 8},        2),
        # Уровень 3
        PathSkill("biz_multiplier", "Районный барон",      "🌍", "×1.25 к доходу районов — твой район, твои правила",         "businessman", 12, {"district_multiplier": 1.25},     3),
        PathSkill("biz_income_4",   "Корпорация",          "🏙", "+25% к доходу — ты уже не просто бизнесмен",                "businessman", 11, {"income_bonus_percent": 25},      3),
        # Уровень 4
        PathSkill("biz_reket",      "Деловая империя",     "👑", "+10% к доходу — абсолютная монополия на рынке",             "businessman", 14, {"income_bonus_percent": 10},      4),
        PathSkill("biz_compound",   "Сложный процент",     "💹", "+25% доход от районов — деньги делают деньги",              "businessman", 13, {"district_multiplier": 1.25},     4),
    ],
    "romantic": [
        # Уровень 0 — базовые
        PathSkill("rom_tickets_1",  "Обаяние",             "💘", "+1 слот тикета — люди тянутся к тебе сами",                "romantic", 3,  {"max_tickets": 1},                  0),
        PathSkill("rom_recruit_1",  "Вербовщик",           "👥", "+25% бойцов при вербовке — умеешь убеждать",               "romantic", 4,  {"recruit_count_bonus": 25},          0),
        # Уровень 1
        PathSkill("rom_recruit_2",   "Харизма",             "💝", "+35% бойцов — твоя улыбка открывает двери",               "romantic", 5,  {"recruit_count_bonus": 35},          1),
        PathSkill("rom_discount_1", "Народная любовь",     "❤️", "-15% стоимость вербовки — люди идут за тобой бесплатно",  "romantic", 5,  {"recruit_discount_percent": 15},     1),
        PathSkill("rom_statist_1",  "Боевая подготовка",   "⚔️", "+10% мощь статистов — ты обучаешь, не только вербуешь",   "romantic", 5,  {"statist_power_bonus": 10},          1),
        # Уровень 2
        PathSkill("rom_recruit_3",  "Мастер вербовки",     "🎯", "+50% бойцов — за тобой идут толпами",                     "romantic", 8,  {"recruit_count_bonus": 50},          2),
        PathSkill("rom_discount_2", "Оптовый вербовщик",   "🏪", "-25% стоимость вербовки — оптом всегда дешевле",           "romantic", 9,  {"recruit_discount_percent": 25},     2),
        PathSkill("rom_tickets_2",  "Легенда харизмы",     "💖", "+2 слота тикета — о тебе слагают легенды",                "romantic", 8,  {"max_tickets": 2},                  2),
        # Уровень 3
        PathSkill("rom_double",     "Двойная вербовка",    "⚡", "Двойная вербовка — два отряда за один раз",                "romantic", 15, {"double_recruit": True},             3),
        PathSkill("rom_recruit_4",  "Легенда вербовки",    "🌟", "+60% бойцов — непревзойдённый рекрутёр",                  "romantic", 12, {"recruit_count_bonus": 60},          3),
        PathSkill("rom_statist_2",  "Элитная гвардия",     "🛡", "+15% мощь статистов — твои бойцы становятся элитой",      "romantic", 11, {"statist_power_bonus": 15},          3),
        # Уровень 4
        PathSkill("rom_recruit_5",  "Армия харизмата",     "👑", "+80% бойцов — твоя армия не знает границ",                "romantic", 15, {"recruit_count_bonus": 80},          4),
        PathSkill("rom_max_ticket", "Звезда удачи",        "🌠", "+1 макс. слот тикета — судьба всегда за тебя",             "romantic", 14, {"max_tickets": 1},                  4),
        PathSkill("rom_statist_3",  "Армия монстров",      "💪", "+20% мощь статистов — твои люди сильнейшие в стране",      "romantic", 14, {"statist_power_bonus": 20},          4),
    ],
    "monster": [
        # Уровень 0 — базовые
        PathSkill("mon_power_1",   "Монстр силы",          "💥", "+15% боевая мощь — твоя банда страшнее всех",               "monster", 5,  {"squad_power_bonus": 15},              0),
        PathSkill("mon_power_2",   "Зверь в клетке",       "🦁", "+10% боевая мощь — сила жаждет выхода",                     "monster", 4,  {"squad_power_bonus": 10},              0),
        # Уровень 1
        PathSkill("mon_power_3",   "Машина войны",         "⚙️", "+20% боевая мощь — ты — живое оружие",                      "monster", 7,  {"squad_power_bonus": 20},              1),
        PathSkill("mon_extra_atk1","Берсерк",              "😤", "+1 доп. атака — ты не останавливаешься, пока враг дышит",   "monster", 6,  {"extra_attack_count": 1},              1),
        PathSkill("mon_trainer_cd","Режим зверя",          "⏱", "-25% КД Том Ли, Чон Гон, Менеджер Ким — монстр не отдыхает","monster", 6,  {"trainer_cd_reduction": 25},           1),
        # Уровень 2
        PathSkill("mon_power_4",   "Пиковая форма",        "🌋", "+30% боевая мощь — предел человеческих возможностей",       "monster", 10, {"squad_power_bonus": 30},              2),
        PathSkill("mon_power_5",   "Непоколебимый",        "🗿", "+20% боевая мощь — тебя уже боятся все вокруг",              "monster", 10, {"squad_power_bonus": 20},              2),
        PathSkill("mon_train_1",   "Стальная воля",        "🏋", "+15% охват тренировки — монстры тренируются иначе",          "monster", 10, {"train_bonus_percent": 15},             2),
        # Уровень 3
        PathSkill("mon_dattack",   "Двойная атака",        "⚔️", "Атака 2 раза в КД — бей пока стоишь",                       "monster", 14, {"double_attack": True},                3),
        PathSkill("mon_power_6",   "Высшая форма",         "👹", "+35% боевая мощь — ты вышел за пределы человеческого",      "monster", 12, {"squad_power_bonus": 35},              3),
        PathSkill("mon_extra_atk2","Неудержимый",          "🔥", "+1 доп. атака — монстры не знают усталости",                "monster", 13, {"extra_attack_count": 1},              3),
        # Уровень 4
        PathSkill("mon_emperor",   "Охотник за бандами",   "👑", "Атаковать одну группировку дважды до КД — безжалостный",    "monster", 15, {"emperor_gang_multi_attack": True},    4),
        PathSkill("mon_extra_atk3","Ярость монстра",       "😱", "+1 доп. атака — всё ещё не остановился",                   "monster", 14, {"extra_attack_count": 1},              4),
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
    ("romantic",    "monster"):   {"name": "Страсть к власти",        "emoji": "🔥", "effect": {"squad_power_bonus": 8},        "desc": "+8% боевая мощь"},
    ("romantic",    "businessman"):{"name": "Богатый покровитель",    "emoji": "💝", "effect": {"recruit_discount_percent": 10},"desc": "-10% стоимость вербовки"},
    ("romantic",    "shadow"):    {"name": "Роковое влечение",        "emoji": "🌹", "effect": {"recruit_count_bonus": 15},     "desc": "+15% вербовка — опасная привлекательность"},
    ("monster",     "businessman"):{"name": "Рэкетир",                "emoji": "😤", "effect": {"income_bonus_percent": 5},     "desc": "+5% доход"},
    ("monster",     "romantic"):  {"name": "Одержимость силой",       "emoji": "👹", "effect": {"squad_power_bonus": 8},        "desc": "+8% боевая мощь"},
    ("monster",     "shadow"):    {"name": "Ночная ярость",           "emoji": "🌑", "effect": {"squad_power_bonus": 7},        "desc": "+7% боевая мощь — удвоенная жестокость"},
    ("shadow",      "businessman"):{"name": "Серый кардинал",         "emoji": "🃏", "effect": {"income_bonus_percent": 5},     "desc": "+5% доход — управляй из тени"},
    ("shadow",      "romantic"):  {"name": "Теневой обаятель",        "emoji": "💫", "effect": {"recruit_count_bonus": 12},     "desc": "+12% вербовка — умеешь убеждать незаметно"},
    ("shadow",      "monster"):   {"name": "Призрак войны",           "emoji": "⚔️", "effect": {"squad_power_bonus": 8},        "desc": "+8% боевая мощь — быстрый и смертоносный"},
}