"""Мастерство — цепочка «Преодоление стены» (конфиг).

Подтверждено пользователем 2026-09-30 (описание + AskUserQuestion): открывается, когда все
четыре характеристики ≥ EXR; задание приходит в случайный момент 1–24 ч после выполнения
условия (и после завершения предыдущего этапа); 4 очка за этап, у тренера Тома Ли — за NHCoin
(деньги бизнеса), 1 покупка = 1 очко; Том = 80/100/120% мощи лагеря атаки игрока на
этапах 1/2/3. Цены очков и цели заданий этапов 2–3 — решение автора кода («сам придумаешь»).
"""
from __future__ import annotations

from bot.constant.characteristic import POTENTIAL_ORDER
from bot.constant.mastery import TASK_EQUAL_WIN, TASK_EXTRAS, TASK_PVP_WINS, TASK_TOM, TASK_TRAININGS

MASTERY_UNLOCK_RANK_INDEX = 33  # CX — все четыре характеристики не ниже (было EXR/40, снижено 2026-10-28)
# Ожидание задания этапа (пользователь 2026-10-28): случайно в диапазоне, чем выше потенциал —
# тем дольше; четких границ у игрока нет. Член банды 2–12 ч … Легенда 2–5 дней, линейно по
# лестнице потенциала; каждый следующий этап ещё × MASTERY_STAGE_DELAY_MULT.
MASTERY_DELAY_HOURS_LOW: tuple[int, int] = (2, 12)  # самый низкий потенциал
MASTERY_DELAY_HOURS_HIGH: tuple[int, int] = (48, 120)  # самый высокий потенциал
MASTERY_STAGE_DELAY_MULT = 1.5


def mastery_delay_range_hours(potential: str | None, stage: int) -> tuple[float, float]:
    """(мин, макс) часов ожидания задания этапа `stage` для потенциала."""
    idx = POTENTIAL_ORDER.index(potential) if potential in POTENTIAL_ORDER else 0
    t = idx / max(1, len(POTENTIAL_ORDER) - 1)
    lo = MASTERY_DELAY_HOURS_LOW[0] + (MASTERY_DELAY_HOURS_HIGH[0] - MASTERY_DELAY_HOURS_LOW[0]) * t
    hi = MASTERY_DELAY_HOURS_LOW[1] + (MASTERY_DELAY_HOURS_HIGH[1] - MASTERY_DELAY_HOURS_LOW[1]) * t
    k = MASTERY_STAGE_DELAY_MULT ** (stage - 1)
    return lo * k, hi * k


# Прорыв перед этапом: сколько достижений из `constant/mastery.BREAKTHROUGHS` нужно (любые).
MASTERY_BREAKTHROUGH_NEED: dict[int, int] = {2: 1, 3: 2}
MASTERY_STAGES = 3  # Стена → Трансцендентность → Мастерство
MASTERY_POINTS_PER_STAGE = 4

# Цена очка у тренера, NHCoin, по этапу (за этап — 4 очка).
MASTERY_POINT_PRICE: dict[int, int] = {1: 50_000, 2: 200_000, 3: 800_000}

# Мощь Тома Ли — % мощи лагеря атаки игрока в момент выдачи задания.
TOM_POWER_PERCENT: dict[int, int] = {1: 80, 2: 100, 3: 120}
TOM_POWER_MIN = 1_000  # если лагерь атаки на момент выдачи пуст
# Том в бою — стопка из N «частей» общей мощью tom_power: движок считает потери по долям
# мощи, одна гигантская единица гибла бы «броском монеты» без накопления урона по раундам.
TOM_COMBAT_UNITS = 1_000

# Задания этапов: (код, цель). Том открывается, когда выполнены все остальные задания этапа.
# 2026-10-28: «квест должен заключаться в тренировках» — тренировки на каждом этапе, растут.
STAGE_TASKS: dict[int, tuple[tuple[str, int], ...]] = {
    1: ((TASK_TRAININGS, 6), (TASK_EXTRAS, 4), (TASK_TOM, 1)),
    2: ((TASK_TRAININGS, 12), (TASK_EXTRAS, 8), (TASK_TOM, 1)),
    3: ((TASK_TRAININGS, 15), (TASK_EXTRAS, 10), (TASK_PVP_WINS, 3), (TASK_EQUAL_WIN, 1), (TASK_TOM, 1)),
}
EQUAL_WIN_POWER_PERCENT = 10  # «победить игрока с мощью ±10% от своей»

MASTERY_SWEEP_INTERVAL_SECONDS = 60
MASTERY_SWEEP_BATCH = 100
