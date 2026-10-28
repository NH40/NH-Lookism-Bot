"""Пробуждение — 10 этапов (конфиг). Формат собственных бафов этапа — `config/development`.

Пользователь 2026-10-02: на этапе **кулака** игрок выполняет квест → открывается
пробуждение; пробуждение **полностью сбрасывает прокачку** (этап, бизнес — «всё»); **10
этапов**; каждый **повышает минимальный потенциал**; каждый даёт **бафы**; главное —
**множитель ко всем бафам** систем развития (кроме мастерства и характеристик); за
пробуждения **падают капли крови** для родословной. Числа, задания квеста и собственные бафы
этапов — решение автора кода («делай, как знаешь, соблюдай баланс»).
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_BOSS_WIN, TASK_PERSONAL_TRAIN, TASK_WAR_WIN, TASK_WIN_PVP

AWAKENING_MAX = 10
AWAKEN_CONFIRM_SECONDS = 30

# Квест кулака на следующий этап: базовые задания × (1 + 0.5 × уже пройденных этапов).
AWAKENING_QUEST_BASE: dict[str, int] = {TASK_BOSS_WIN: 4, TASK_WIN_PVP: 3, TASK_WAR_WIN: 1, TASK_PERSONAL_TRAIN: 10}


def awakening_quest(next_level: int) -> dict[str, int]:
    k = 1 + 0.5 * (next_level - 1)
    return {task: max(1, round(n * k)) for task, n in AWAKENING_QUEST_BASE.items()}


# Капли крови за пробуждение — основной источник для родословной (боссы — лишь редкая добыча).
def awakening_blood_drops(new_level: int) -> int:
    return 10 + 2 * new_level  # 12 за 1-е … 30 за 10-е, всего 210


# Пол потенциала: этап N гарантирует стадию не ниже N-й по `POTENTIAL_ORDER` (0 — Член
# банды … 7 — Легенда). С 7-го этапа потенциал всегда «Легенда».
def potential_floor_index(level: int) -> int:
    return min(7, level)


# Собственные бафы этапов (сверх множителя). Сам множитель на них не действует.
def _c(**kw) -> dict:
    return {"combat": kw}


def _e(**kw) -> dict:
    return {"eco": kw}


LEVELS: tuple[dict, ...] = (
    _e(dev_points=0.10),
    _e(fragment_bonus=0.15),
    _e(income=0.05),
    _e(blood_bonus=0.25),
    _e(army_power=0.05),
    _e(ticket_cap=2, ticket_regen=0.10),
    _e(battle_cooldown=0.10),
    _e(stat_cost_discount=0.10),
    _c(loss_save=0.05),
    {"combat": {"durability": 0.05}, "eco": {"army_power": 0.10}},
)


# Смена страны после пробуждения (пользователь 2026-10-28): кнопка живёт столько и только пока
# у игрока нет районов (после пробуждения их нет — прогресс сброшен).
RELOCATE_WINDOW_SECONDS = 24 * 60 * 60
