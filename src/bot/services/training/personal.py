"""Личная тренировка — очки развития для характеристик (сервис).

raw-notes «Тренировки»: «личная тренировка в зависимости от потенциала даёт очков, есть
шанс в зависимости от потенциала, что игрок не получит ничего... получив очки, игрок в
профиле поднимает себе характеристики». Пользователь 2026-09-30: КД около часа, очки зависят
от потенциала (таблица — `config/characteristic.POTENTIAL_TRAINING`).

КД — `SET NX EX` в Redis (правило 2 и сама механика ожидания одним ключом, как у вербовки):
ставится ДО начисления, двойной клик второй раз не пройдёт. Неудача («ничего не вышло») КД
тоже тратит — это попытка тренировки, а не её отсутствие.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.unique_path import bump_training_reps
from bot.constant.cooldown import CD_PERSONAL
from bot.services.cooldown import schedule as schedule_ready
from bot.cache.keys import personal_training_cooldown
from bot.config.characteristic import POTENTIAL_TRAINING
from bot.config.game import PERSONAL_TRAINING_COOLDOWN_SECONDS
from bot.db.repositories import characteristic as char_repo
from bot.constant.dev_quest import TASK_PERSONAL_TRAIN
from bot.services.dev_quest import emit as quest_event
from bot.services.characteristic import ensure_potential, get_combat_profile
from bot.services.mastery import record_training
from bot.services.training.training import TrainingOnCooldownError


@dataclass(frozen=True, slots=True)
class PersonalTrainResult:
    points: int  # 0 — «ничего не вышло»
    dev_points: int  # баланс после тренировки
    potential: str
    cooldown_seconds: int


async def train_personal(
    session: AsyncSession, redis: Redis, user_id: int, rng: random.Random | None = None
) -> PersonalTrainResult:
    rng = rng or random
    key = personal_training_cooldown(user_id)
    profile = await get_combat_profile(session, user_id)
    cooldown = profile.cooldown(PERSONAL_TRAINING_COOLDOWN_SECONDS, profile.eco.personal_cooldown)
    if not await redis.set(key, "1", nx=True, ex=cooldown):
        raise TrainingOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))
    await schedule_ready(redis, user_id, CD_PERSONAL, cooldown)

    potential = await ensure_potential(session, user_id)
    table = POTENTIAL_TRAINING[potential]
    points = 0 if rng.random() * 100 < table.nothing_percent else rng.randint(table.min_points, table.max_points)
    if points and profile.eco.dev_points:
        # Бонус систем развития (Самдак, гений тренировок): дробная часть — вероятностно.
        boosted = points * (1 + profile.eco.dev_points)
        points = int(boosted) + (1 if rng.random() < boosted - int(boosted) else 0)
    # Задание цепочки мастерства (этап 2: N личных тренировок) — засчитывается любая
    # тренировка, даже без очков: это попытка, а не результат.
    await record_training(session, user_id)
    await quest_event(session, user_id, TASK_PERSONAL_TRAIN)
    balance = await char_repo.add_points(session, user_id, points) if points else (
        await char_repo.get_stats(session, user_id)
    ).dev_points
    await bump_training_reps(session, user_id)
    await session.commit()
    return PersonalTrainResult(
        points=points, dev_points=balance, potential=potential, cooldown_seconds=cooldown
    )


async def personal_cooldown_left(redis: Redis, user_id: int) -> int:
    """Сколько секунд до следующей личной тренировки (0 — можно)."""
    return max(0, await redis.ttl(personal_training_cooldown(user_id)))
