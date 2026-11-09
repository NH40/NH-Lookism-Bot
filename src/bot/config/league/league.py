"""Лиги (пользователь 2026-11-09): пять ступеней, у каждой своя копия карты.

Счёт учитывает всё: мощь, донат, ранги, мастерство, пробуждения, потенциал, родословные, второе тело, техники,
гениев и путь. Пороги подобраны по игрокам, активным за 3 дня на 2026-11-09 (45 / 25 / 15 / 10 / 5%), и меняются
в админке. Переход только вверх: иначе сильный игрок мог бы слить армию и пойти к новичкам."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LeagueDef:
    index: int
    name: str


LEAGUES: tuple[LeagueDef, ...] = (
    LeagueDef(0, "2 поколение"),
    LeagueDef(1, "1 поколение"),
    LeagueDef(2, "1.5 поколение"),
    LeagueDef(3, "0 поколение"),
    LeagueDef(4, "Легенды"),
)
# Счёт, с которого начинается лига (индекс — лига).
LEAGUE_THRESHOLDS: tuple[int, ...] = (0, 210, 300, 380, 540)
# Бафф за каждую ступень выше первой.
LEAGUE_INCOME_STEP = 0.10
LEAGUE_POWER_STEP = 0.05
# Ежедневный пересчёт: первый проход после этого часа UTC (21 UTC — полночь по Москве).
LEAGUE_SWEEP_HOUR_UTC = 21
LEAGUE_SWEEP_TICK_SECONDS = 300

# Веса счёта.
SCORE_POWER_LOG = 40  # за каждый порядок мощи армии
SCORE_DONATE_LOG = 25  # за каждый порядок суммы доната, ₽
SCORE_STAT_RANK = 1
SCORE_MASTERY = 5
SCORE_AWAKENING = 15
SCORE_POTENTIAL = 3
SCORE_BLOODLINE_LEVEL = 4
SCORE_SECOND_BODY = 30
SCORE_TECHNIQUE_LEVEL = 1
SCORE_GENIUS_LEVEL = 1
SCORE_PATH_LEVEL = 2


def league_for_score(score: int) -> int:
    league = 0
    for index, threshold in enumerate(LEAGUE_THRESHOLDS):
        if score >= threshold:
            league = index
    return league


def next_league(league: int) -> tuple[LeagueDef, int] | None:
    """Следующая лига и её порог; None — уже Легенды."""
    if league + 1 >= len(LEAGUES):
        return None
    return LEAGUES[league + 1], LEAGUE_THRESHOLDS[league + 1]
