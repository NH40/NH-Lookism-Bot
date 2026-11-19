"""Рейды (баланс, пользователь 2026-11-19).

Сложность — от мощи армии игрока: бот-отряд = доля его мощи. За час — пуш: встретить лагерем атаки или
не отвечать — тогда бьётся лагерь защиты. Победа — пак ресурсов (с кровью), поражение — районы уходят ботам
(лёгкий 1, средний 2, сложный 3), здания на них сгорают. До 3 рейдов в сутки, не чаще раза в 4 часа.
"""
from __future__ import annotations

from bot.constant.resource import RES_BLOOD, RES_COINS, RES_PATH_FRAGMENTS, RES_TECHNIQUE_FRAGMENTS, RES_TICKETS

RAID_EASY, RAID_MEDIUM, RAID_HARD = "easy", "medium", "hard"
RAID_DIFFICULTIES: dict[str, tuple[int, float, int]] = {  # вес выпадения, доля мощи игрока, районов при поражении
    RAID_EASY: (50, 0.5, 1),
    RAID_MEDIUM: (35, 0.8, 2),
    RAID_HARD: (15, 1.1, 3),
}
RAID_REWARDS: dict[str, dict[str, int]] = {
    RAID_EASY: {RES_COINS: 2_000, RES_TICKETS: 1, RES_BLOOD: 1},
    RAID_MEDIUM: {RES_COINS: 6_000, RES_TICKETS: 2, RES_BLOOD: 2, RES_TECHNIQUE_FRAGMENTS: 3},
    RAID_HARD: {RES_COINS: 15_000, RES_TICKETS: 4, RES_BLOOD: 4, RES_TECHNIQUE_FRAGMENTS: 5, RES_PATH_FRAGMENTS: 3},
}
RAID_WARNING_SECONDS = 3600
RAID_PER_DAY = 3
RAID_MIN_GAP_HOURS = 4
RAID_ACTIVE_DAYS = 3  # только тем, кто заходил за 3 дня
RAID_SWEEP_SECONDS = 600
RAID_CHANCE_PER_SWEEP = 2.5 / (24 * 3600 / RAID_SWEEP_SECONDS)  # ≈ 2–3 в сутки на подходящего игрока
RAID_STACK_SIZE = 50  # отряд бота — одна стопка из 50 бойцов
