"""Зелья (конфиг).

Пользователь 2026-10-04: «магазин зелий… на зелья должен влиять гений медицины… придумай
сам, не бойся масштабов, сделай прям красиво, можешь посмотреть приятные моменты из 1.0».
Из 1.0 взяты тиры зелий (там — I–VI по шести видам), один активный эффект на вид и
авто-зелья гения медицины. Виды переложены на системы 2.0: каждое зелье — временный
источник тех же бафов, что у систем развития (`services/build`), поэтому действует везде,
где эти бафы читаются. Числа и цены — решение автора кода.

Тиры: I–II доступны всем; III–VII открывает **гений медицины** (активный, по уровням —
`config/genius`: поле `potion_tier`). Он же делает зелья дешевле (`potion_discount`), дольше
(`potion_duration`), сильнее (`potion_power`) и даёт слоты **авто-зелий** (`potion_auto`) —
выбранное зелье само покупается и выпивается заново, когда кончается.
"""
from __future__ import annotations

from bot.constant.potion import (
    POTION_GUARD,
    POTION_HUNTER,
    POTION_LUCK,
    POTION_POWER,
    POTION_RECRUIT,
    POTION_TRAINING,
    POTION_WEALTH,
)

POTION_TIERS = 7
POTION_BASE_MAX_TIER = 2  # без гения медицины
POTION_DISCOUNT_CAP = 0.6

# Цена тира (NHCoin): ×3 за ступень. Кафе приносит ~14 400 🪙 в сутки — I тир по карману с
# первого дня, VII — расходник императора.
POTION_PRICES: tuple[int, ...] = (1_500, 4_500, 13_500, 40_000, 120_000, 360_000, 1_080_000)


def _tiers(combat: dict[str, tuple] | None = None, eco: dict[str, tuple] | None = None) -> tuple[dict, ...]:
    """Значения по тирам → спеки уровней (формат систем развития: {"combat": …, "eco": …})."""
    combat, eco = combat or {}, eco or {}
    specs = []
    for i in range(POTION_TIERS):
        spec = {}
        c = {k: v[i] for k, v in combat.items() if v[i]}
        e = {k: v[i] for k, v in eco.items() if v[i]}
        if c:
            spec["combat"] = c
        if e:
            spec["eco"] = e
        specs.append(spec)
    return tuple(specs)


# Вид → (длительность, мин; эффекты тиров I…VII). Эффект тира — НЕ накопительный: выпитый
# тир заменяет прежний (один активный эффект на вид, как в 1.0).
POTION_EFFECTS: dict[str, tuple[int, tuple[dict, ...]]] = {
    POTION_POWER: (30, _tiers(combat={
        "attack": (0.05, 0.10, 0.16, 0.23, 0.31, 0.40, 0.52),
        "durability": (0.03, 0.05, 0.08, 0.12, 0.16, 0.20, 0.26),
    })),
    POTION_GUARD: (30, _tiers(combat={
        "loss_save": (0.03, 0.06, 0.09, 0.13, 0.17, 0.22, 0.28),
        "reduction": (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07),
    })),
    POTION_WEALTH: (60, _tiers(eco={
        "income": (0.10, 0.20, 0.32, 0.45, 0.60, 0.80, 1.00),
    })),
    POTION_TRAINING: (60, _tiers(eco={
        "extras_training": (2, 4, 6, 9, 12, 15, 20),  # п.п. к шансам тренировки статистов
        "dev_points": (0.10, 0.20, 0.30, 0.45, 0.60, 0.80, 1.00),
    })),
    POTION_RECRUIT: (45, _tiers(eco={
        "recruit_double": (0.05, 0.10, 0.15, 0.20, 0.26, 0.32, 0.40),
        "recruit_rank_bonus": (0, 0, 0, 0, 1, 1, 2),
    })),
    POTION_LUCK: (30, _tiers(eco={
        "gacha_luck": (0.02, 0.04, 0.06, 0.08, 0.10, 0.13, 0.16),
        "gacha_free_roll": (0.02, 0.04, 0.05, 0.07, 0.09, 0.11, 0.14),
    })),
    POTION_HUNTER: (60, _tiers(eco={
        "fragment_bonus": (0.10, 0.20, 0.30, 0.40, 0.52, 0.65, 0.80),
    })),
}

# Авто-зелья: фоновый проход раз в минуту продлевает зелья, которые кончились или кончатся
# в ближайшую минуту.
POTION_AUTO_SWEEP_SECONDS = 60
