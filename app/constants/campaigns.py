"""
Балансные константы системы Походов.
Все цифры вынесены сюда — меняй свободно (для донатов, балансировки и т.д.).
"""
from dataclasses import dataclass

# ── Глобальные лимиты ─────────────────────────────────────────────────────────

# Максимум одновременных активных походов на игрока
MAX_ACTIVE_CAMPAIGNS: int = 3

# Максимальный шанс успешного сбора ресурсов (%)
MAX_SUCCESS_CHANCE: int = 80

# Минимальный шанс успешного сбора ресурсов (%) — даже слабый поход
MIN_SUCCESS_CHANCE: int = 5

# Максимальный процент вернувшихся статистов
MAX_SURVIVAL_RATE: int = 90

# ── Длительность похода ───────────────────────────────────────────────────────

# Доступные варианты длительности в часах
CAMPAIGN_DURATIONS_HOURS: list[int] = [2, 3, 6, 12]

# ── Ранги заданий ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CampaignRankConfig:
    rank: str
    label: str
    emoji: str
    # Мощь одного статиста, при которой power_ratio = 1 (100% вклад)
    required_power_per_statist: int
    # Базовый шанс успеха (%) при power_ratio = 0
    base_success_chance: int
    # Множитель финальной награды
    reward_multiplier: float


CAMPAIGN_RANKS: list[CampaignRankConfig] = [
    CampaignRankConfig("E", "E", "⬜",     100,  60, 1.0),
    CampaignRankConfig("D", "D", "🟦",     500,  50, 1.5),
    CampaignRankConfig("C", "C", "🟩",   1_500,  40, 2.5),
    CampaignRankConfig("B", "B", "🟨",   5_000,  35, 4.0),
    CampaignRankConfig("A", "A", "🟧",  15_000,  30, 6.0),
    CampaignRankConfig("S", "S", "🟥",  50_000,  20, 10.0),
]

CAMPAIGN_RANK_MAP: dict[str, CampaignRankConfig] = {r.rank: r for r in CAMPAIGN_RANKS}

# ── Ресурсы ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CampaignResourceConfig:
    resource_id: str           # поле на модели User, куда начисляется
    label: str
    emoji: str
    # Базовая награда за 1 статиста за 1 час при успехе и reward_mult=1.0
    base_per_statist_per_hour: float


CAMPAIGN_RESOURCES: list[CampaignResourceConfig] = [
    CampaignResourceConfig("nh_coins",         "NHCoin",              "💰", 25),
    CampaignResourceConfig("card_dust",        "Пыль",                "💎",   0.005),
    CampaignResourceConfig("ui_fragments",     "Фрагменты УИ",        "🔮",   0.001),
    CampaignResourceConfig("alchemy_fragments","Фрагменты алхимии",   "🧪",   0.001),
    CampaignResourceConfig("path_fragments",   "Фрагменты Пути",      "⚡",   0.001),
]

CAMPAIGN_RESOURCE_MAP: dict[str, CampaignResourceConfig] = {
    r.resource_id: r for r in CAMPAIGN_RESOURCES
}

# ── Формула успеха ────────────────────────────────────────────────────────────
#
#   power_ratio = avg_power / required_power_per_statist
#   success_chance = clamp(base_success_chance + power_ratio * POWER_BONUS_FACTOR,
#                          MIN_SUCCESS_CHANCE, MAX_SUCCESS_CHANCE)

# Сколько % добавляет каждая единица power_ratio к шансу успеха
POWER_BONUS_FACTOR: int = 20

# ── Формула выживаемости ──────────────────────────────────────────────────────
#
# При успехе:
#   survival_pct = clamp(BASE_SURVIVAL_ON_SUCCESS + power_ratio * SURVIVAL_FACTOR,
#                        MIN_SURVIVAL_SUCCESS, MAX_SURVIVAL_RATE)
# При провале:
#   survival_pct = clamp(BASE_SURVIVAL_ON_FAIL + power_ratio * SURVIVAL_FACTOR_FAIL,
#                        MIN_SURVIVAL_FAIL, MAX_SURVIVAL_RATE // 2)

# Базовый процент выживших при успехе (power_ratio=0)
BASE_SURVIVAL_ON_SUCCESS: int = 50

# Бонус к выживаемости за каждую единицу power_ratio (при успехе)
SURVIVAL_FACTOR: int = 15

# Минимальный % выживших при успехе
MIN_SURVIVAL_SUCCESS: int = 10

# Базовый процент выживших при провале (power_ratio=0)
BASE_SURVIVAL_ON_FAIL: int = 10

# Бонус к выживаемости при провале за единицу power_ratio
SURVIVAL_FACTOR_FAIL: int = 5

# Минимальный % выживших при провале
MIN_SURVIVAL_FAIL: int = 0

# ── Выбор количества статистов (кнопки) ──────────────────────────────────────
# Фиксированные варианты, которые предлагаются игроку. Значения — абсолютное число.
# Если у игрока меньше статистов, кнопка скрывается.
STATIST_COUNT_OPTIONS: list[int] = [1, 5, 10, 25, 50, 100]

# Максимум статистов в одном походе
MAX_STATISTS_PER_CAMPAIGN: int = 200
