# ── Уровни карточек ─────────────────────────────────────────────────────────
# Множитель мощи карточки в зависимости от уровня
LEVEL_MULTIPLIERS: dict[int, float] = {
    0: 1.0,    # базовая мощь
    1: 6.5,    # базовая мощь + 550%
    2: 17.5,   # базовая мощь + 1650%
    3: 51.0,   # базовая мощь + 5000%
}

LEVEL_LABELS: dict[int, str] = {
    0: "Ур.0",
    1: "Ур.1 ✦",
    2: "Ур.2 ✦✦",
    3: "Ур.3 ✦✦✦",
}

LEVEL_EMOJIS: dict[int, str] = {
    0: "⬜",
    1: "🟦",
    2: "🟨",
    3: "🌟",
}

# ── Слияние (fusion) ─────────────────────────────────────────────────────────
# Сколько карточек уровня N нужно для получения одной карточки уровня N+1
FUSION_COST: dict[int, int] = {
    0: 5,   # 5 × Ур.0  → 1 × Ур.1
    1: 3,   # 3 × Ур.1  → 1 × Ур.2
    2: 3,   # 3 × Ур.2  → 1 × Ур.3
}

# ── Пыль (dust) ──────────────────────────────────────────────────────────────
# Базовое количество пыли за распыление — зависит от РАНГА карточки
DUST_BY_RANK: dict[str, int] = {
    "member":       1,
    "boss":         1,
    "king":         2,
    "strong_king":  5,
    "gen_zero":     14,
    "new_legend":   35,
    "legend":       100,
    "peak":         350,
    "absolute":     1_250,
    "perfection":   5_000,
}

# Множитель по уровню карточки: базовая_пыль × level_factor
DUST_LEVEL_FACTOR: dict[int, float] = {
    0: 1.0,
    1: 2.5,
    2: 7.0,
    3: 20.0,
}

# Для обратной совместимости (если где-то используется DUST_PER_LEVEL напрямую)
DUST_PER_LEVEL: dict[int, int] = {
    0: 10,
    1: 30,
    2: 100,
    3: 300,
}


def calc_dust(rank: str, level: int) -> int:
    """Вычислить количество пыли за распыление карточки (ранг + уровень)."""
    base = DUST_BY_RANK.get(rank, 10)
    factor = DUST_LEVEL_FACTOR.get(level, 1.0)
    return max(1, int(base * factor))

# Стоимость крафта одного тикета в пыли
TICKET_CRAFT_COST = 50

# ── Боты-дуэлянты ────────────────────────────────────────────────────────────
BOT_TIERS: dict[str, dict] = {
    "gen2": {
        "name": "Лига 2-го поколения",
        "emoji": "🥉",
        "allowed_ranks": ["member", "boss", "king", "strong_king"],
        # веса уровней: level 0, 1, 2, 3
        "level_weights": [50, 40, 9, 1],
        "dust_min": 30,
        "dust_max": 70,
    },
    "gen1": {
        "name": "Лига 1-го поколения",
        "emoji": "🥈",
        "allowed_ranks": ["king", "strong_king", "gen_zero", "new_legend"],
        "level_weights": [20, 40, 30, 10],
        "dust_min": 70,
        "dust_max": 130,
    },
    "gen0": {
        "name": "Лига нулевого поколения",
        "emoji": "🥇",
        "allowed_ranks": ["new_legend", "legend", "peak", "absolute"],
        "level_weights": [5, 25, 40, 30],
        "dust_min": 120,
        "dust_max": 220,
    },
}

# Максимальный уровень карточки
CARD_MAX_LEVEL: int = 3

# КД дуэли с ботом (секунды) — сокращается мастерством скорости
DUEL_BOT_CD_BASE: int = 15 * 60  # 15 минут
# КД PvP-дуэли (секунды) — для обоих участников после завершения
DUEL_PVP_CD_BASE: int = 15 * 60  # 15 минут
# Минимальный КД дуэлей после всех скидок
DUEL_MIN_CD: int = 3 * 60  # 3 минуты
# Снижение КД дуэлей за донат-титул «Карточный мастер» (%)
DUEL_DONAT_CD_REDUCTION: int = 20

# Время жизни PvP-вызова в Redis (секунды)
DUEL_CHALLENGE_TTL: int = 90

# Размер колоды для дуэли
DUEL_DECK_SIZE: int = 5
DUEL_RANDOM_SIZE: int = 5  # +5 случайных из остатка коллекции
