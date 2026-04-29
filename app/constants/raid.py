# Боссы кланов
RAID_BOSSES = {
    "yamazaki": {
        "name": "Клан Ямадзаки",
        "emoji": "⛩️",
        "bosses": {
            "gun": {
                "id": "gun",
                "name": "Ямадзаки Ган",
                "emoji": "⚔️",
                "description": "Наносит урон равный боевой мощи УНИКАЛЬНЫХ ПЕРСОНАЖЕЙ",
                "damage_source": "characters",  # урон от персонажей
                "base_hp": 5_000_000_000,
                "reward_fragments": "ui",
                "cd_hours": 6,
                "raid_duration_seconds": 3600,  # 1 час
            },
            "shingen": {
                "id": "shingen",
                "name": "Ямадзаки Шинген",
                "emoji": "🏯",
                "description": "Наносит урон равный боевой мощи СТАТИСТОВ",
                "damage_source": "squad",  # урон от статистов
                "base_hp": 3_000_000_000,
                "reward_fragments": "ui",
                "cd_hours": 6,
                "raid_duration_seconds": 3600,
            },
        }
    }
}

# УИ крафт — стоимость в фрагментах
UI_CRAFT_COST = {
    1: 50,    # 1 уровень УИ
    2: 150,   # 2 уровень
    3: 350,   # 3 уровень
    4: 700,   # 4 уровень (донат даёт сразу)
}

# УИ уровни — что дают
UI_LEVEL_PERKS = {
    1: {"name": "УИ I",  "perk": "Авто-вербовка",              "field": "ui_auto_recruit"},
    2: {"name": "УИ II", "perk": "Авто-тренировка",            "field": "ui_auto_train"},
    3: {"name": "УИ III","perk": "Авто-тикеты",                "field": "ui_auto_ticket"},
    4: {"name": "УИ IV", "perk": "Авто-прокрутка персонажей",  "field": "ui_auto_pull"},
}

RAID_ATTACK_CD_SECONDS = 300  # 5 минут между атаками
RAID_ATTACK_CD_KEY = "raid_attack:{raid_id}:{user_id}"