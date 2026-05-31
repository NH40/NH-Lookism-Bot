TOM_LEE_COST = 3_000_000
TOM_LEE_CD_SECONDS = 7200
TOM_LEE_POINTS_MIN = 1
TOM_LEE_POINTS_MAX = 3

JEON_GON_COST = 1_000_000
JEON_GON_CD_SECONDS = 7200
JEON_GON_POINTS_MIN = 2
JEON_GON_POINTS_MAX = 5

MANAGER_KIM_COST = 5_000_000
MANAGER_KIM_CD_SECONDS = 7200
MANAGER_KIM_POINTS_MIN = 1
MANAGER_KIM_POINTS_MAX = 3

# ── Гений войны: стоимость каждого уровня в очках войны ──────────────────────
WAR_GENIUS_LEVEL_COSTS = [100, 300, 1000, 2000, 5000]

# Какой босс открывается на каждом уровне Гения войны (авто-рейд)
WAR_GENIUS_BOSS_MAP = {
    1: ("yamazaki", "shingen"),
    2: ("yamazaki", "gun"),
    3: ("zero_gen", "jinnen"),
    4: ("zero_gen", "gauren"),
    5: ("zero_gen", "elite"),
}

WAR_GENIUS_BOSS_LABELS = {
    1: "⚔️ Шинген (Ямадзаки)",
    2: "⚔️ Ган Ямадзаки",
    3: "🌑 Джинен",
    4: "🔷 Гапрен",
    5: "👑 Элита",
}

TRAINERS = [
    {
        "id": "tom_lee",
        "name": "Том Ли",
        "emoji": "🥋",
        "description": (
            "Гений боя. В его время все ходили со всеми порогами. "
            "За скромную плату поможет прокачать мастерство и боевую мощь."
        ),
        "photo": "images/teacher/Tom_Le.png",
        "cost": TOM_LEE_COST,
        "cd": TOM_LEE_CD_SECONDS,
        "reward": f"{TOM_LEE_POINTS_MIN}-{TOM_LEE_POINTS_MAX} очков мастерства",
    },
    {
        "id": "jeon_gon",
        "name": "Чон Гон",
        "emoji": "🧘",
        "description": (
            "Гений тренировок. Двое из его учеников открыли уникальный путь. "
            "Кто знает, может и ты откроешь свой. Даёт очки пути."
        ),
        "photo": None,
        "cost": JEON_GON_COST,
        "cd": JEON_GON_CD_SECONDS,
        "reward": f"{JEON_GON_POINTS_MIN}-{JEON_GON_POINTS_MAX} очков пути",
    },
    {
        "id": "manager_kim",
        "name": "Менеджер Ким",
        "emoji": "💼",
        "description": (
            "Стратег и тактик нулевого поколения. Знает о войне всё. "
            "Тренировки у него стоят дорого, но дают очки войны — "
            "валюту для прокачки навыка «Гений войны», который откроет "
            "автоматические атаки в рейдах по кулдауну."
        ),
        "photo": "images/teacher/Meneger_Kim.png",
        "cost": MANAGER_KIM_COST,
        "cd": MANAGER_KIM_CD_SECONDS,
        "reward": f"{MANAGER_KIM_POINTS_MIN}-{MANAGER_KIM_POINTS_MAX} очков войны",
    },
]