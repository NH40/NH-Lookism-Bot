"""Тренировки — тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (сервис).

Личная тренировка (очки развития по потенциалу, КД 1 час) — соседний файл `personal.py`.

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
from random import binomialvariate, choices, shuffle

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin.live_config import cooldown_seconds
from bot.constant.admin.live_config import KEY_CD_EXTRAS
from bot.db.repositories.unique_path import bump_training_reps
from bot.constant.cooldown import CD_EXTRAS
from bot.services.cooldown import schedule as schedule_ready
from bot.cache.keys import train_extras_cooldown
from bot.config.game import (
    EXTRA_TRAINING_COVERAGE_PERCENT,
    EXTRA_TRAINING_MAX_STARS,
    EXTRA_TRAINING_STAGE1_SUCCESS_PERCENT,
    EXTRA_TRAINING_STAGE2_SUCCESS_PERCENT,
    EXTRA_TRAINING_STAGE3_SUCCESS_PERCENT,
)
from bot.config.characteristic import training_level_cap
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.db.repositories.extra import add_to_stack, list_stacks
from bot.constant.dev_quest import TASK_TRAIN_EXTRAS
from bot.services.dev_quest import emit as quest_event
from bot.services.business import gym_training_bonus_percent
from bot.services.characteristic import get_combat_profile
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
    index = max(RANK_INDEX[rank], min(RANK_INDEX[rank] + 1, PHASE_RANK_CAP_INDEX[phase]))
    return RANK_LADDER[index]


def _is_maxed(rank: str, level: int, phase: str) -> bool:
    """На капе и идти некуда (Infinity или потолок фазы): больше не растёт и не тренируется."""
    return level >= training_level_cap(rank) and _next_rank(rank, phase) == rank


def _after_level_up(rank: str, level: int, phase: str) -> tuple[str, int]:
    """Куда попадает боец с новым уровнем `level` (пользователь 2026-11-04): дошёл до капа ранга —
    обязательно следующий ранг с уровнем 0 (звёзды остаются); следующего нет — стоит на капе."""
    cap = training_level_cap(rank)
    if level < cap:
        return rank, level
    target = _next_rank(rank, phase)
    return (target, 0) if target != rank else (rank, cap)


def _coverage(stacks, phase: str, fraction: float) -> list[int]:
    """Сколько бойцов каждой стопки попало в тренировку. Выпавшие бойцы на максимуме не тренируются —
    вместо них берутся другие случайные статисты (пользователь 2026-11-04), поэтому их доля
    раздаётся по остальным стопкам пропорционально числу ещё не попавших бойцов."""
    covered = [binomialvariate(s.quantity, fraction) for s in stacks]
    free = [i for i, s in enumerate(stacks) if not _is_maxed(s.rank, s.training_level, phase)]
    spare = sum(c for i, c in enumerate(covered) if i not in free)
    covered = [c if i in free else 0 for i, c in enumerate(covered)]
    shuffle(free)
    left = sum(stacks[i].quantity - covered[i] for i in free)
    for i in free:
        if spare <= 0 or left <= 0:
            break
        room = stacks[i].quantity - covered[i]
        extra = min(room, binomialvariate(spare, room / left))
        covered[i] += extra
        spare -= extra
        left -= room
    return covered


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

    trainable = [s for s in stacks if not _is_maxed(s.rank, s.training_level, phase)]
    if not trainable:
        # Все на максимуме — тренировать некого, КД не тратим (как и при пустой армии).
        return TrainResult(attempted=0, stage1=0, stage2=0, stage3=0)

    profile = await get_combat_profile(session, user_id)
    cd = profile.cooldown(cooldown_seconds(KEY_CD_EXTRAS), profile.eco.extras_training_cooldown)
    acquired = await redis.set(key, "1", nx=True, ex=cd)
    if not acquired:
        ttl = await redis.ttl(key)
        raise TrainingOnCooldownError(retry_after_seconds=max(0, ttl))
    await schedule_ready(redis, user_id, CD_EXTRAS, cd)

    coverage_fraction = EXTRA_TRAINING_COVERAGE_PERCENT / 100
    # Тренажёрные залы: +1 п.п. к шансу КАЖДОГО из трёх этапов за здание (подтверждено
    # 2026-09-29), шанс не выше 100%. Охват (сколько статистов попадает в тренировку)
    # зал не трогает — только успешность.
    # + бонус систем развития (гений тренировок, путь тренировок, Самдак) — в тех же п.п.
    gym_bonus = await gym_training_bonus_percent(session, user_id) + profile.eco.extras_training
    stage1_p = min(100, EXTRA_TRAINING_STAGE1_SUCCESS_PERCENT + gym_bonus) / 100
    stage2_p = min(100, EXTRA_TRAINING_STAGE2_SUCCESS_PERCENT + gym_bonus) / 100
    stage3_p = min(100, EXTRA_TRAINING_STAGE3_SUCCESS_PERCENT + gym_bonus) / 100

    totals = {"attempted": 0, "stage1": 0, "stage2": 0, "stage3": 0}

    covered_by_stack = _coverage(stacks, phase, coverage_fraction)
    if not any(covered_by_stack):
        # Мало статистов, разбросанных по отрядам: охват 20% мог не задеть никого — тогда игрок
        # видел «нечего тренировать», а КД уже потрачен (баг 2026-10-13). Хотя бы один боец —
        # случайный, с весом по численности отряда — тренируется всегда.
        pick = choices(trainable, weights=[s.quantity for s in trainable])[0]
        covered_by_stack[next(i for i, s in enumerate(stacks) if s is pick)] = 1

    for stack, covered in zip(stacks, covered_by_stack):
        if covered == 0:
            continue
        totals["attempted"] += covered

        s1 = binomialvariate(covered, stage1_p)
        # Путь тренировок: не прошедшие пробуют ещё раз «у другого учителя».
        if profile.eco.extras_extra_roll and covered > s1:
            s1 += binomialvariate(covered - s1, stage1_p * min(1.0, profile.eco.extras_extra_roll))
        if s1 == 0:
            continue
        totals["stage1"] += s1
        # Лагерь при тренировке не меняется — стопка-назначение в том же лагере.
        common = {"user_id": user_id, "camp": stack.camp, "school": stack.school, "school_level": stack.school_level}
        # Новый уровень: на капе — следующий ранг с нуля. Стопки старше правила (уровень уже выше капа)
        # переходят при первом же успехе.
        next_rank, next_level = _after_level_up(stack.rank, stack.training_level + 1, phase)
        await add_to_stack(
            session, **common, rank=stack.rank, stars=stack.stars, training_level=stack.training_level, quantity=-s1
        )

        if stack.stars >= EXTRA_TRAINING_MAX_STARS:
            # Уже максимум звёзд — этап 2 пропускается целиком (raw-notes), весь s1
            # просто поднимает уровень тренировки без звезды.
            await add_to_stack(
                session, **common, rank=next_rank, stars=stack.stars, training_level=next_level, quantity=s1
            )
            continue

        s2 = binomialvariate(s1, stage2_p)
        await add_to_stack(
            session, **common, rank=next_rank, stars=stack.stars, training_level=next_level, quantity=s1 - s2
        )
        if s2 == 0:
            continue
        totals["stage2"] += s2

        s3 = binomialvariate(s2, stage3_p)
        await add_to_stack(
            session, **common, rank=next_rank, stars=stack.stars + 1, training_level=next_level, quantity=s2 - s3
        )
        if s3:
            totals["stage3"] += s3
            # Удачный ранг этапа 3 — тот же переход, что по капу: следующий ранг и уровень с нуля. Если
            # боец и так только что перешёл по капу — ещё один ранг сверху; выше потолка фазы — остаётся.
            lucky_rank = _next_rank(next_rank, phase)
            await add_to_stack(
                session, **common, rank=lucky_rank, stars=stack.stars + 1,
                training_level=0 if lucky_rank != next_rank else next_level, quantity=s3,
            )

    await quest_event(session, user_id, TASK_TRAIN_EXTRAS)
    from bot.services.mastery import record_extras_training  # мастерство → тренировки: ленивый импорт

    await record_extras_training(session, user_id)
    await bump_training_reps(session, user_id)
    await session.commit()
    return TrainResult(**totals)
