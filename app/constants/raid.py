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
        }
    },
}

ALCHEMY_CRAFT_COST = 80
ALCHEMY_MAX_FRAGMENTS_PER_RAID = 25

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