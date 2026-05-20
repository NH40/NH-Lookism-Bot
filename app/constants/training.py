TOM_LEE_COST = 3_000_000
TOM_LEE_CD_SECONDS = 7200
TOM_LEE_POINTS_MIN = 0
TOM_LEE_POINTS_MAX = 0

JEON_GON_COST = 1_000_000
JEON_GON_CD_SECONDS = 7200
JEON_GON_POINTS_MIN = 2
JEON_GON_POINTS_MAX = 5

TRAINERS = [
    {
        "id": "tom_lee",
        "name": "Том Ли",
        "emoji": "🥋",
        "description": "Мастер боевых искусств — очки мастерства",
        "cost": TOM_LEE_COST,
        "cd": TOM_LEE_CD_SECONDS,
        "reward": f"{TOM_LEE_POINTS_MIN}-{TOM_LEE_POINTS_MAX} очков мастерства",
    },
    {
        "id": "jeon_gon",
        "name": "Чон Гон",
        "emoji": "🧘",
        "description": "Наставник пути — очки пути",
        "cost": JEON_GON_COST,
        "cd": JEON_GON_CD_SECONDS,
        "reward": f"{JEON_GON_POINTS_MIN}-{JEON_GON_POINTS_MAX} очков пути",
    },
]