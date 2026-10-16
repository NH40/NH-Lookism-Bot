"""Школы учителей статистов (конфиг).

Пользователь 2026-10-03: на карте в случайный момент появляется учитель статистов (пуш
игрокам); даёт задание; выполнил — учитель появляется в магазине («Обучение»); купил —
открывается обучение у него; каждое занятие тоже стоит денег, но меньше самого учителя.
Учителя — Бэкхо (сила), Хансу (техника), Элита (ловкость), Мусаши (скорость); обучение выводит
статистов в школу и даёт им бафы. Уровни школы, бафы, цены и задания — решение автора кода.
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_BOSS_WIN, TASK_RECRUIT, TASK_TRAIN_EXTRAS, TASK_WIN_PVE, TASK_WIN_PVP
from bot.constant.school import SCHOOL_AGILITY, SCHOOL_SPEED, SCHOOL_STRENGTH, SCHOOL_TECHNIQUE

SCHOOL_MAX_LEVEL = 5

# Бафы бойца школы за каждый её уровень — у каждой стопки свои (`CombatStack`).
SCHOOL_POWER_PER_LEVEL: dict[str, float] = {SCHOOL_STRENGTH: 0.08, SCHOOL_SPEED: 0.02}
SCHOOL_DODGE_PER_LEVEL: dict[str, float] = {SCHOOL_AGILITY: 0.03}
SCHOOL_FLEE_PER_LEVEL: dict[str, float] = {SCHOOL_SPEED: 0.02}
SCHOOL_BLOCK_PER_LEVEL: dict[str, float] = {SCHOOL_TECHNIQUE: 0.03}
SCHOOL_COUNTER_PER_LEVEL: dict[str, float] = {SCHOOL_SPEED: 0.02, SCHOOL_TECHNIQUE: 0.01}

# Квест учителя на карте.
SCHOOL_QUESTS: dict[str, dict[str, int]] = {
    SCHOOL_STRENGTH: {TASK_WIN_PVE: 6, TASK_TRAIN_EXTRAS: 4, TASK_BOSS_WIN: 1},
    SCHOOL_AGILITY: {TASK_TRAIN_EXTRAS: 6, TASK_WIN_PVP: 2, TASK_RECRUIT: 10},
    SCHOOL_SPEED: {TASK_WIN_PVP: 3, TASK_WIN_PVE: 4, TASK_TRAIN_EXTRAS: 3},
    SCHOOL_TECHNIQUE: {TASK_TRAIN_EXTRAS: 5, TASK_BOSS_WIN: 2, TASK_WIN_PVE: 3},
}

# Магазин: учитель — разовая покупка, занятие — каждое за деньги и с перерывом.
SCHOOL_TEACHER_PRICE = 150_000
SCHOOL_LESSON_PRICE = 15_000
SCHOOL_LESSON_COOLDOWN_SECONDS = 60 * 60

# Занятие: охват статистов и шансы. Новички без школы вступают в неё (1-й уровень), ученики
# этой же школы — поднимают её уровень. Тренажёрные залы и бафы тренировки тоже помогают.
SCHOOL_COVERAGE_PERCENT = 20
SCHOOL_JOIN_PERCENT = 25
SCHOOL_LEVEL_UP_PERCENT = 15

# Появление учителя статистов на карте — реже учителей техник.
SCHOOL_TEACHER_SPAWN_CHANCE_PER_TICK = 300 / (6 * 60 * 60)
SCHOOL_TEACHER_DURATION_SECONDS = 2 * 60 * 60
