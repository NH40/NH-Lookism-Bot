"""Мастерство — цепочка «Преодоление стены» (конфиг).

Подтверждено пользователем 2026-09-30 (описание + AskUserQuestion): открывается, когда все
четыре характеристики ≥ EXR; задание приходит в случайный момент 1–24 ч после выполнения
условия (и после завершения предыдущего этапа); 4 очка за этап, у тренера Тома Ли — за NHCoin
(деньги бизнеса), 1 покупка = 1 очко; Том = 80/100/120% мощи лагеря атаки игрока на
этапах 1/2/3. Цены очков и цели заданий этапов 2–3 — решение автора кода («сам придумаешь»).
"""
from __future__ import annotations

from bot.constant.mastery import TASK_EQUAL_WIN, TASK_PVP_WINS, TASK_TOM, TASK_TRAININGS

MASTERY_UNLOCK_RANK_INDEX = 40  # EXR — все четыре характеристики не ниже
MASTERY_QUEST_DELAY_MIN_SECONDS = 1 * 3600
MASTERY_QUEST_DELAY_MAX_SECONDS = 24 * 3600
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
STAGE_TASKS: dict[int, tuple[tuple[str, int], ...]] = {
    1: ((TASK_TOM, 1),),
    2: ((TASK_TRAININGS, 10), (TASK_TOM, 1)),
    3: ((TASK_PVP_WINS, 3), (TASK_EQUAL_WIN, 1), (TASK_TOM, 1)),
}
EQUAL_WIN_POWER_PERCENT = 10  # «победить игрока с мощью ±10% от своей»

MASTERY_SWEEP_INTERVAL_SECONDS = 60
MASTERY_SWEEP_BATCH = 100
