RAID_BOSSES = {
    "yamazaki": {
        "name": "Клан Ямадзаки",
        "emoji": "⛩️",
        "description": (
            "Японский клан якудза, в котором течёт невероятная кровь монстров. "
            "Сразись с Широ Они и Тора Они дабы пробудить древнюю кровь клана."
        ),
        "bosses": {
            "gun": {
                "id": "gun",
                "name": "Ямадзаки Ган",
                "emoji": "⚔️",
                "description": "Широ Они — дабы победить Гана необходимо собрать невероятную команду из уникальных персонажей.",
                "damage_source": "characters",
                "base_hp": 3_000_000_000,
                "reward_fragments": "ui",
                "cd_hours": 6,
                "raid_duration_seconds": 3600,
            },
            "shingen": {
                "id": "shingen",
                "name": "Ямадзаки Шинген",
                "emoji": "🏯",
                "description": "Тора Они — глава клана. Дабы сразиться с ним необходимо собрать армию статистов.",
                "damage_source": "squad",
                "base_hp": 500_000_000,
                "reward_fragments": "ui",
                "cd_hours": 6,
                "raid_duration_seconds": 3600,
            },
        }
    },
    "zero_gen": {
        "name": "Нулевое поколение",
        "emoji": "🌑",
        "description": (
            "Легенды, их эпоху называли эпохой войн, те кто защитили Корею от Ямадзаки. "
            "Боевая мощь каждого участника делится на 2 — таков барьер нулевого поколения."
        ),
        "bosses": {
            "jinnen": {
                "id": "jinnen",
                "name": "Джинен",
                "emoji": "🌑",
                "description": (
                    "Один из сильнейших бойцов нулевого поколения. Зеркальный король. "
                    "Атаковать его может любой, но твоя боевая мощь делится на 2."
                ),
                "damage_source": "combat_power",
                "combat_power_divisor": 2,
                "base_hp": 2_000_000_000,
                "reward_fragments": "alchemy",
                "cd_hours": 6,
                "raid_duration_seconds": 3600,
            },
            "gauren": {
                "id": "gauren",
                "name": "Гапрен",
                "emoji": "🔷",
                "description": (
                    "Молчаливый страж пути. Легенда, постигшая все известные техники. "
                    "Сразить его — значит прикоснуться к сокровенным знаниям нулевого поколения. "
                    "Твоя боевая мощь делится на 3."
                ),
                "damage_source": "combat_power",
                "combat_power_divisor": 3,
                "base_hp": 2_500_000_000,
                "reward_fragments": "path",
                "cd_hours": 3,
                "raid_duration_seconds": 3600,
            },
            "elite": {
                "id": "elite",
                "name": "Элита",
                "emoji": "👑",
                "description": (
                    "Нулевое поколение в зените силы. Элита — обладатель невидимых атак, второй в Кулаках Гапрена после самого Гапрена"
                    "чья боевая мощь в 2 раза превышает твою. Победа над ними открывает доступ "
                    "к бизнес-знаниям, которые позволят расширить империю без долгих завоеваний."
                ),
                "damage_source": "combat_power",
                "combat_power_divisor": 2,
                "base_hp": 1_000_000_000,
                "reward_fragments": "business",
                "cd_hours": 6,
                "raid_duration_seconds": 3600,
            },
        }
    },
}

ALCHEMY_MAX_FRAGMENTS_PER_RAID = 80

# ── Бизнес-фрагменты ─────────────────────────────────────────────────────────
BUSINESS_FRAGMENTS_MAX_PER_RAID = 25

# Стоимость крафта одного бонусного района (экспансия без захвата городов)
BUSINESS_DISTRICT_COST = 50
# Максимум бонусных районов через крафт
BUSINESS_DISTRICTS_MAX = 50

# ── Гений бизнеса (5 уровней) ─────────────────────────────────────────────────
# Стоимость каждого уровня в бизнес-фрагментах
BIZ_GENIUS_COSTS = [50, 150, 350, 750, 1500]

# Накопительный бонус к доходу со всех зданий (% на каждом уровне)
BIZ_GENIUS_INCOME_BONUS = [20, 45, 75, 110, 160]

# Описания уровней Гения бизнеса
BIZ_GENIUS_LEVEL_LABELS = {
    1: "Малый элитный бизнес 🗼",
    2: "Средний элитный бизнес 🌆",
    3: "Крупный элитный бизнес 💎",
    4: "Мегабизнес 🌍",
    5: "Легендарный бизнес 👑",
}

# Название специальной механики (Бизнес-экспансия: бонусные районы)
BIZ_EXPANSION_LABEL = "🏘 Бизнес-экспансия (бонусные районы)"

PATH_SPIN_CRAFT_COST = 40
PATH_FRAGMENTS_MAX_PER_RAID = 20

UI_CRAFT_COST = {
    1: 50,
    2: 150,
    3: 350,
    4: 700,
}

UI_LEVEL_PERKS = {
    1: {"name": "УИ I",   "perk": "Авто-вербовка",             "field": "ui_auto_recruit"},
    2: {"name": "УИ II",  "perk": "Авто-тренировка",           "field": "ui_auto_train"},
    3: {"name": "УИ III", "perk": "Авто-тикеты",               "field": "ui_auto_ticket"},
    4: {"name": "УИ IV",  "perk": "Авто-прокрутка персонажей", "field": "ui_auto_pull"},
}

RAID_ATTACK_CD_SECONDS = 300
RAID_ATTACK_CD_KEY = "raid_attack:{raid_id}:{user_id}"

# ── Уровни сложности рейд-боссов (5 тиров) ───────────────────────────────────
# Тир 3 — текущие боссы, открыт по умолчанию.
# Высший тир = больше HP, меньше награды (ниже ratio → меньше фрагментов).
# Низший тир = меньше HP, больше награды.

BOSS_TIER_COUNT = 5
BOSS_TIER_DEFAULT = 3

# Множители HP относительно base_hp (тир 3 = ×1.0)
BOSS_TIER_HP_MULT: dict[int, float] = {
    1: 0.2,
    2: 0.5,
    3: 1.0,
    4: 2.5,
    5: 6.0,
}

# Стоимость разблокировки в очках войны (тир 3 = бесплатен)
BOSS_TIER_UNLOCK_COST: dict[int, int] = {
    1: 5,
    2: 10,
    3: 0,
    4: 20,
    5: 25,
}

BOSS_TIER_NAMES: dict[int, str] = {
    1: "Низший",
    2: "Слабый",
    3: "Обычный",
    4: "Сильный",
    5: "Легендарный",
}

BOSS_TIER_EMOJIS: dict[int, str] = {
    1: "⬇️",
    2: "🔽",
    3: "▶️",
    4: "🔼",
    5: "⬆️",
}

# ── Уровни пути ───────────────────────────────────────────────────────────────
PATH_LEVEL_COSTS = [20, 40, 80, 150, 300]   # стоимость уровня 1→2→3→4→5 в фрагментах
PATH_LEVEL_MAX = 5

# Бонус за каждый уровень пути (накопительный)
PATH_LEVEL_BONUSES: dict[str, dict] = {
    "businessman": {"income_bonus_percent": 5},
    "romantic":    {"ticket_chance": 3},
    "monster":     {"train_bonus_percent": 5},
}

# Бонус за Пробуждение (получение всех навыков основного пути)
PATH_AWAKENING_BONUSES: dict[str, dict] = {
    "businessman": {"income_bonus_percent": 20},
    "romantic":    {"max_tickets": 1, "ticket_chance": 5},
    "monster":     {"train_bonus_percent": 20},
}