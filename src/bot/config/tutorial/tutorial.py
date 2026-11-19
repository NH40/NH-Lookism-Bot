"""Лига-обучение (баланс, пользователь 2026-11-19).

Личная учебная страна: 3 города. Посёлок берётся по районам (как банда), Город и Столица — целиком одним боем
(как круг), Столица делает императором учебной страны. Боты слабые: новичку на старт дают учебный отряд.
Награды скромные — за весь гайд примерно день обычной игры новичка, выдаются один раз.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.constant.resource import (
    RES_BLOOD,
    RES_COINS,
    RES_DEV_POINTS,
    RES_GENIUS_FRAGMENTS,
    RES_PATH_FRAGMENTS,
    RES_TECHNIQUE_FRAGMENTS,
    RES_TICKETS,
)

# Учебная карта: (название, районов, ранг ботов, ботов; whole — город берётся одним боем).
@dataclass(frozen=True, slots=True)
class TrainingCity:
    name: str
    districts: int
    bot_rank: str
    bots: int
    whole: bool


TRAINING_CITIES: tuple[TrainingCity, ...] = (
    TrainingCity("Учебный посёлок", 4, "F-", 3, False),  # за район
    TrainingCity("Учебный город", 5, "F-", 25, True),  # весь город
    TrainingCity("Учебная столица", 6, "F-", 40, True),  # весь город → император
)
TRAINING_START_SQUAD = ("F-", 10)  # учебный отряд новичку на старт (в лагерь атаки)
TRAINING_BATTLE_COOLDOWN_SECONDS = 20  # свой короткий КД, настоящий КД сражений не тратится
TRAINING_INCOME_CAP_MINUTES = 24 * 60

# Шаги: код, награда. Порядок — пользователь 2026-11-19.
STEP_FIGHT = "fight"  # захватить район посёлка
STEP_BUILD = "build"  # построить кафе
STEP_INCOME = "income"  # забрать доход
STEP_RECRUIT = "recruit"  # нанять статистов (настоящая вербовка)
STEP_POWER = "power"  # 3 района посёлка
STEP_DEVELOP = "develop"  # поднять характеристику (настоящее развитие)
STEP_BLOODLINE = "bloodline"  # выбрать родословную (настоящий выбор)
STEP_GENIUS = "genius"  # урок
STEP_TECHNIQUE = "technique"  # урок
STEP_MASTERY = "mastery"  # урок про «Преодоление стены»
STEP_CITY = "city"  # весь посёлок + Учебный город целиком
STEP_COUNTRY = "country"  # Столица → император учебной страны

TRAINING_STEPS: tuple[str, ...] = (
    STEP_FIGHT, STEP_BUILD, STEP_INCOME, STEP_RECRUIT, STEP_POWER, STEP_DEVELOP,
    STEP_BLOODLINE, STEP_GENIUS, STEP_TECHNIQUE, STEP_MASTERY, STEP_CITY, STEP_COUNTRY,
)
TRAINING_LESSONS: frozenset[str] = frozenset({STEP_GENIUS, STEP_TECHNIQUE, STEP_MASTERY})  # закрываются кнопкой «Понятно»
# Мастерство — урок: «Преодоление стены» открывается от рангов характеристик, у новичка его может ещё не быть.

TRAINING_REWARDS: dict[str, dict[str, int]] = {
    STEP_FIGHT: {RES_COINS: 1_000},
    STEP_BUILD: {RES_TICKETS: 1},
    STEP_INCOME: {RES_COINS: 2_000},
    STEP_RECRUIT: {RES_DEV_POINTS: 3},  # на следующий шаг «Развитие»
    STEP_POWER: {RES_COINS: 3_000, RES_TICKETS: 2},
    STEP_DEVELOP: {RES_DEV_POINTS: 2},
    STEP_BLOODLINE: {RES_BLOOD: 3},
    STEP_GENIUS: {RES_GENIUS_FRAGMENTS: 5},
    STEP_TECHNIQUE: {RES_TECHNIQUE_FRAGMENTS: 5},
    STEP_MASTERY: {RES_COINS: 3_000},
    STEP_CITY: {RES_COINS: 5_000, RES_TICKETS: 3},
    STEP_COUNTRY: {RES_COINS: 10_000, RES_TICKETS: 5, RES_PATH_FRAGMENTS: 5},
}
TRAINING_POWER_DISTRICTS = 3  # шаг «Мощь»: столько районов посёлка
