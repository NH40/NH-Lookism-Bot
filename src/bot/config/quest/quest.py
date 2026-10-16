"""Ежедневные задания (конфиг).

Пользователь 2026-10-04: «список из 100 задач, каждый день игроку приходит 10; можно
переролить все 10 либо 2 на выбор» (механика LBP1: `app/constants/quests.py` — 100 заданий,
9 в день, замены и полный реролл); «у каждой задачи своё количество опыта — сложные дают
много, лёгкие мало»; выполненное задание сразу даёт опыт Battle Pass (`config/battle_pass`).
Реролл бесплатный, новый набор — в 00:00 по Москве (AskUserQuestion). Состав пула и числа —
решение автора кода.
"""
from __future__ import annotations

from datetime import timedelta, timezone

from bot.constant.dev_quest import (
    TASK_BOSS_WIN,
    TASK_BP_CLAIM,
    TASK_BUILD,
    TASK_CASINO,
    TASK_CLAN_DONATE,
    TASK_COLLECT,
    TASK_CONTRACT,
    TASK_DEPOSIT,
    TASK_DEV_LEVEL,
    TASK_EXCHANGE_DEAL,
    TASK_EXCHANGE_LIST,
    TASK_GARRISON,
    TASK_INCOME,
    TASK_PERSONAL_TRAIN,
    TASK_POKER_HAND,
    TASK_POTION,
    TASK_PVP_CHALLENGE,
    TASK_RECRUIT,
    TASK_ROLL,
    TASK_SCHOOL_LESSON,
    TASK_STAT_INVEST,
    TASK_STORAGE,
    TASK_TRAIN_EXTRAS,
    TASK_WIN_PVE,
    TASK_WIN_PVP,
)

QUESTS_PER_DAY = 10
# День заданий и дневного буста пасса — по Москве (UTC+3, без перехода на летнее время).
QUEST_DAY_TZ = timezone(timedelta(hours=3))
QUEST_SWAPS_PER_DAY = 2  # замены по одному заданию (вместо полного реролла)
QUEST_REPEAT_DAYS = 3  # задание не выдаётся снова столько дней (LBP1 — 10 при 9 из 100)

# Сложность: лёгкое, среднее, сложное, эпическое → опыт Battle Pass.
QUEST_TIER_XP: tuple[int, ...] = (20, 40, 70, 110)
QUEST_TIER_NAMES: tuple[str, ...] = ("лёгкое", "среднее", "сложное", "эпическое")
# Вес сложности при выдаче: лёгких больше, эпических меньше.
QUEST_TIER_WEIGHTS: tuple[int, ...] = (4, 3, 2, 1)

# 25 видов действий × 4 сложности = 100 заданий. Вид → цели по сложностям.
QUEST_TARGETS: dict[str, tuple[int, int, int, int]] = {
    TASK_WIN_PVE: (2, 5, 9, 15),
    TASK_WIN_PVP: (1, 2, 3, 5),
    TASK_BOSS_WIN: (1, 2, 3, 4),
    TASK_PERSONAL_TRAIN: (1, 3, 5, 8),
    TASK_TRAIN_EXTRAS: (1, 3, 5, 8),
    TASK_RECRUIT: (10, 30, 80, 200),  # статистов
    TASK_ROLL: (1, 3, 6, 10),
    TASK_COLLECT: (1, 2, 4, 6),
    TASK_BUILD: (1, 2, 3, 5),
    TASK_SCHOOL_LESSON: (1, 2, 3, 5),
    TASK_POTION: (1, 2, 3, 5),
    TASK_CASINO: (2, 5, 10, 20),
    TASK_POKER_HAND: (1, 3, 6, 12),
    TASK_EXCHANGE_DEAL: (1, 2, 3, 5),
    TASK_EXCHANGE_LIST: (1, 2, 3, 5),
    TASK_DEPOSIT: (1, 2, 3, 4),
    TASK_STORAGE: (1, 2, 3, 5),
    TASK_CONTRACT: (1, 2, 3, 4),
    TASK_CLAN_DONATE: (1, 2, 3, 5),
    TASK_GARRISON: (1, 2, 3, 5),
    TASK_STAT_INVEST: (1, 3, 6, 10),  # рангов
    TASK_DEV_LEVEL: (1, 2, 3, 5),
    TASK_PVP_CHALLENGE: (1, 2, 3, 4),
    TASK_BP_CLAIM: (1, 3, 6, 10),  # уровней
    TASK_INCOME: (3_000, 10_000, 30_000, 80_000),  # NHCoin
}

# Задания, которые выдаются только тем, кому они физически доступны.
QUEST_NEEDS_CLAN: frozenset[str] = frozenset({TASK_CLAN_DONATE, TASK_GARRISON})
QUEST_NEEDS_SCHOOL: frozenset[str] = frozenset({TASK_SCHOOL_LESSON})


def quest_code(task: str, tier: int) -> str:
    return f"{task}:{tier}"


# Пул: код → (событие, цель, сложность 0–3, опыт).
QUEST_POOL: dict[str, tuple[str, int, int, int]] = {
    quest_code(task, tier): (task, targets[tier], tier, QUEST_TIER_XP[tier])
    for task, targets in QUEST_TARGETS.items()
    for tier in range(4)
}
assert len(QUEST_POOL) == 100
