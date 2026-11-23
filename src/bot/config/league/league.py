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
# 2026-11-10: пороги подняты (было 0/210/300/380/540) — новички слишком легко доходили до Легенд.
# Уже перешедших не понижаем: смена лиги снимает территорию.
# 2026-11-19: 0/300/600/800/1000 (пользователь; на проде те же значения уже стояли в админке).
LEAGUE_THRESHOLDS: tuple[int, ...] = (0, 300, 600, 800, 1000)
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
# 2026-11-19: доход и клан. Доход в час — логарифмом, как мощь (вес подобран симуляцией на живых данных);
# клан — прибавка каждому участнику за место клана в топе.
SCORE_INCOME_LOG = 20  # за каждый порядок дохода в час, NHCoin
SCORE_CLAN_TOP3 = 100
SCORE_CLAN_TOP10 = 60
SCORE_CLAN_TOP25 = 30


# Лиги по реальной силе (пользователь 2026-11-23): две оси со статичными порогами — мощь армии и сила развития
# (вся прокачка, `services/top/dev_score`). Лига — старшая из двух: перерос порог по любой оси — выше. Донат не
# считается отдельно (он и так превращается в мощь и прокачку). Пока выключатель 0 — работает прежний счёт; пороги
# подбираются по предпросмотру в админке (распределение мощи и СР по лигам), потом выключатель → 1.
LEAGUE_STATIC_AXES = 0
LEAGUE_POWER_THRESHOLDS: tuple[int, ...] = (0, 1_000_000, 10_000_000, 100_000_000, 500_000_000)
LEAGUE_DEV_THRESHOLDS: tuple[int, ...] = (0, 150, 350, 600, 900)
# Вниз — только неактивный (пользователь 2026-11-23): не заходил столько дней и по силе уже ниже своей лиги — на одну
# лигу за пересчёт, территория уходит ботам. Только при включённых лигах по силе.
LEAGUE_INACTIVE_DAYS = 14


def _by(thresholds: tuple[int, ...], value: float) -> int:
    league = 0
    for index, threshold in enumerate(thresholds):
        if value >= threshold:
            league = index
    return league


def league_for_axes(power: float, dev: float) -> int:
    """Лига по двум осям — старшая из лиги по мощи и лиги по силе развития."""
    return max(_by(LEAGUE_POWER_THRESHOLDS, power), _by(LEAGUE_DEV_THRESHOLDS, dev))


def axes_progress(league: int, power: float, dev: float) -> tuple[int, int, int, int, float] | None:
    """До следующей лиги по силе: (мощь, нужно мощи, СР, нужно СР, лучшая доля 0..1). None — Легенды."""
    if league + 1 >= len(LEAGUES):
        return None
    need_p, need_d = LEAGUE_POWER_THRESHOLDS[league + 1], LEAGUE_DEV_THRESHOLDS[league + 1]
    best = max(min(1.0, power / need_p) if need_p else 1.0, min(1.0, dev / need_d) if need_d else 1.0)
    return int(power), int(need_p), int(dev), int(need_d), best


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


def league_bonus(league: int) -> tuple[int, int]:
    """Бафф лиги в процентах: (доход, атака и прочность)."""
    return round(league * LEAGUE_INCOME_STEP * 100), round(league * LEAGUE_POWER_STEP * 100)


def league_progress(league: int, score: int) -> tuple[int, int] | None:
    """Прогресс внутри лиги: (набрано, нужно). None — Легенды, выше лиг нет."""
    following = next_league(league)
    if following is None:
        return None
    floor = LEAGUE_THRESHOLDS[league]
    need = following[1] - floor
    return min(max(score - floor, 0), need), need
