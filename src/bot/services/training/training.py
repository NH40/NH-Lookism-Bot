"""Тренировки — личная (характеристики, КД 10 минут) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (сервис).

**Личная тренировка — НЕ реализована.** Раскладка баллов/шанса ничего-не-получить в
raw-notes целиком завязана на «Потенциал», чей стартовый разброс и механика влияния
пользователь сам ещё не решил ("изначально рандомно... уточню где влияет позже", см.
CLAUDE.md "Открытые вопросы дизайна") — додумывать эту формулу сейчас не стали.

**Тренировка статистов реализована** — единственный этап raw-notes, у которого БАЗОВЫЕ
числа даны явно (10%/20%/×1.2/+50%/25%) и НЕ требуют потенциала (см. `config/game.py`).

**Переработано 2026-09-21 под масштаб "сотни миллиардов статистов" (AskUserQuestion,
подтверждено пользователем)**: статисты хранятся СТОПКАМИ (`db/models/extra.py`), не по
одной строке на статиста — значит тренировка не может кидать один случайный бросок на
каждого юнита (при миллиардах это физически не посчитать). Вместо этого на КАЖДУЮ
стопку — один `random.binomialvariate(n, p)` (стандартная библиотека Python 3.12+,
эффективно моделирует "сколько из n независимых испытаний с шансом p успешны" без
цикла по n) — статистически эквивалентно честному броску за каждого, но за одну
операцию хоть для 5, хоть для 500 миллиардов.
"""
from __future__ import annotations

from dataclasses import dataclass
from random import binomialvariate

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import train_extras_cooldown
from bot.config.game import (
    EXTRA_TRAINING_COOLDOWN_SECONDS,
    EXTRA_TRAINING_COVERAGE_PERCENT,
    EXTRA_TRAINING_MAX_STARS,
    EXTRA_TRAINING_STAGE1_SUCCESS_PERCENT,
    EXTRA_TRAINING_STAGE2_SUCCESS_PERCENT,
    EXTRA_TRAINING_STAGE3_SUCCESS_PERCENT,
)
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.db.repositories.extra import add_to_stack, list_stacks
from bot.services.recruit import PHASE_RANK_CAP_INDEX


class TrainingOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class TrainResult:
    attempted: int
    stage1: int
    stage2: int
    stage3: int


def _next_rank(rank: str, phase: str) -> str:
    """Следующая ступень `RANK_LADDER`, не выше потолка фазы (та же граница, что у
    вербовки, см. `services/recruit`) — если статист уже на потолке, остаётся на месте."""
    index = min(RANK_INDEX[rank] + 1, PHASE_RANK_CAP_INDEX[phase])
    return RANK_LADDER[index]


async def train_extras(session: AsyncSession, redis: Redis, user_id: int, phase: str) -> TrainResult:
    """Атомарный `SET NX EX` — тот же приём, что у вербовки. Если у игрока вообще нет
    статистов — КД НЕ тратится (нечего тренировать, это не действие, а его отсутствие).

    По каждой стопке: `covered = binomialvariate(stack.quantity, coverage%)` — сколько
    единиц ИЗ ЭТОЙ стопки попало в тренировку в этот раз. Дальше три биномиальных
    броска подряд, каждый — ТОЛЬКО над теми, кто прошёл предыдущий (воронка, как в
    raw-notes): `stage1 = binomialvariate(covered, 10%)`, `stage2 = binomialvariate(
    stage1, 10%)` (только если ещё <3 звёзд), `stage3 = binomialvariate(stage2, 25%)`.
    Результат каждого этапа — не отдельные юниты, а КОЛИЧЕСТВО, переносимое из
    исходной стопки в стопку-назначение (ранг/звёзды/уровень тренировки +1 по
    соответствующей оси) одним атомарным upsert на назначение (`add_to_stack`,
    отрицательное `quantity` на списание с исходной стопки, положительное — на
    зачисление в стопку-назначение; несколько стопок могут дать общее назначение —
    `add_to_stack` их сложит через `ON CONFLICT DO UPDATE`, не перезапишет)."""
    key = train_extras_cooldown(user_id)
    stacks = await list_stacks(session, user_id, for_update=True)
    if not stacks:
        return TrainResult(attempted=0, stage1=0, stage2=0, stage3=0)

    acquired = await redis.set(key, "1", nx=True, ex=EXTRA_TRAINING_COOLDOWN_SECONDS)
    if not acquired:
        ttl = await redis.ttl(key)
        raise TrainingOnCooldownError(retry_after_seconds=max(0, ttl))

    coverage_fraction = EXTRA_TRAINING_COVERAGE_PERCENT / 100
    stage1_p = EXTRA_TRAINING_STAGE1_SUCCESS_PERCENT / 100
    stage2_p = EXTRA_TRAINING_STAGE2_SUCCESS_PERCENT / 100
    stage3_p = EXTRA_TRAINING_STAGE3_SUCCESS_PERCENT / 100

    totals = {"attempted": 0, "stage1": 0, "stage2": 0, "stage3": 0}

    for stack in stacks:
        covered = binomialvariate(stack.quantity, coverage_fraction)
        if covered == 0:
            continue
        totals["attempted"] += covered

        s1 = binomialvariate(covered, stage1_p)
        if s1 == 0:
            continue
        totals["stage1"] += s1
        await add_to_stack(
            session, user_id=user_id, rank=stack.rank, stars=stack.stars, training_level=stack.training_level,
            quantity=-s1,
        )

        if stack.stars >= EXTRA_TRAINING_MAX_STARS:
            # Уже максимум звёзд — этап 2 пропускается целиком (raw-notes), весь s1
            # просто поднимает уровень тренировки без звезды.
            await add_to_stack(
                session, user_id=user_id, rank=stack.rank, stars=stack.stars,
                training_level=stack.training_level + 1, quantity=s1,
            )
            continue

        s2 = binomialvariate(s1, stage2_p)
        no_star = s1 - s2
        if no_star:
            await add_to_stack(
                session, user_id=user_id, rank=stack.rank, stars=stack.stars,
                training_level=stack.training_level + 1, quantity=no_star,
            )
        if s2 == 0:
            continue
        totals["stage2"] += s2

        s3 = binomialvariate(s2, stage3_p)
        star_no_rank = s2 - s3
        if star_no_rank:
            await add_to_stack(
                session, user_id=user_id, rank=stack.rank, stars=stack.stars + 1,
                training_level=stack.training_level + 1, quantity=star_no_rank,
            )
        if s3:
            totals["stage3"] += s3
            next_rank = _next_rank(stack.rank, phase)
            await add_to_stack(
                session, user_id=user_id, rank=next_rank, stars=stack.stars + 1,
                training_level=stack.training_level + 1, quantity=s3,
            )

    await session.commit()
    return TrainResult(**totals)
