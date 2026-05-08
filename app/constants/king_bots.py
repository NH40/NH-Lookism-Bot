# Имена ботов-королей
KING_BOT_NAMES = [
    "Банда Чёрного Орла",
    "Группировка Стального Кулака",
    "Клан Красного Дракона",
    "Братство Железной Горы",
    "Союз Северного Ветра",
]

# Прогрессия ботов по слотам — мощь задаётся как множитель от боевой мощи игрока
KING_BOT_SLOTS = [
    {"slot": 1, "power_ratio": 0.50, "districts": 8,  "cd_hours": 1},
    {"slot": 2, "power_ratio": 0.70, "districts": 16, "cd_hours": 1},
    {"slot": 3, "power_ratio": 0.90, "districts": 16, "cd_hours": 1},
    {"slot": 4, "power_ratio": 1.10, "districts": 32, "cd_hours": 1},
    {"slot": 5, "power_ratio": 1.30, "districts": 32, "cd_hours": 1},
]

# Минимальная мощь бота (если мощь игрока ещё мала)
KING_BOT_MIN_POWER = 500

# Рост мощи после полного захвата (множитель)
KING_BOT_POWER_GROWTH = 1.5