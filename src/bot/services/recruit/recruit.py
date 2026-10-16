"""Вербовка — статисты (по влиянию, КД 20 минут) и уникальные персонажи (за тикеты) (сервис).

Уникальные персонажи — TODO, требуют доменов `card`/`gacha` (перки, редкости и т.п. в
raw-notes не сведены в реализуемую механику, см. CLAUDE.md "Открытые вопросы дизайна") —
пока реализована ТОЛЬКО вербовка статистов.

**Формула ранга подтверждена пользователем 2026-09-21 (AskUserQuestion)**: raw-notes
дают только стартовое влияние (10) и потолок ранга по фазам (F..EX/EXR/ZZZ), но не саму
зависимость влияния от диапазона — этот пробел был явно отмечен в CLAUDE.md как открытый
вопрос. Подтверждённое правило: вербовка даёт СЛУЧАЙНЫЙ ранг от F- до потолка, где
потолок = min(потолок фазы, влияние-й индекс в лестнице рангов) — то есть чем больше
влияние, тем выше шанс на редкого статиста, но всегда возможен и F-.
"""
from __future__ import annotations

from dataclasses import dataclass
from random import randint, random

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import recruit_extra_cooldown
from bot.config.characteristic import extra_power_for_rank
from bot.config.game import RECRUIT_EXTRA_COOLDOWN_SECONDS
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG
from bot.constant.dev_quest import TASK_RECRUIT
from bot.services.dev_quest import emit as quest_event
from bot.services.district import get_influence
from bot.services.extra import recruit_into_stack
from bot.services.characteristic import get_combat_profile

# Потолок ранга статиста по фазе игрока (raw-notes «Карта») — 0-based индекс в
# RANK_LADDER, не сам ранг: банда F..EX, круг F..EXR, кулак F..ZZZ (каждый следующий
# шире предыдущего, включает его целиком).
PHASE_RANK_CAP_INDEX: dict[str, int] = {
    PHASE_GANG: RANK_INDEX["EX"],
    PHASE_CIRCLE: RANK_INDEX["EXR"],
    PHASE_FIST: RANK_INDEX["ZZZ"],
}


class RecruitOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class RecruitResult:
    rank: str
    power: int


def recruit_ceiling_rank(phase: str, influence: int) -> str:
    """Лучший ранг, который вообще может выпасть при вербовке: min(потолок фазы, влияние)."""
    return RANK_LADDER[min(PHASE_RANK_CAP_INDEX[phase], influence)]


def roll_extra_rank(phase: str, influence: int, rank_bonus: int = 0) -> str:
    """Влияние считается от захваченных районов (`services/district.get_influence`, +1 за
    район) — каждый захваченный район поднимает потолок вербовки на одну ступень.
    `rank_bonus` — ступени сверх потолка от систем развития (Джинчоль, гений войны):
    поднимает и потолок влияния, и потолок фазы — «военные вербуют лучше»."""
    ceiling_index = min(PHASE_RANK_CAP_INDEX[phase] + rank_bonus, influence + rank_bonus, len(RANK_LADDER) - 1)
    return RANK_LADDER[randint(0, ceiling_index)]


async def recruit_extra(session: AsyncSession, redis: Redis, user_id: int, phase: str) -> RecruitResult:
    """Атомарный `SET NX EX` — сам ключ и есть КД (правило 4, см. `cache/keys.
    recruit_extra_cooldown`): если он не взят, вербовка недоступна ещё
    `retry_after_seconds`. Единственный шаг после — +1 к стопке (ранг, 0, 0),
    коммитит здесь один раз (правило 10 — это top-level операция, не композируется
    ни с чем ещё)."""
    key = recruit_extra_cooldown(user_id)
    profile = await get_combat_profile(session, user_id)
    acquired = await redis.set(key, "1", nx=True, ex=profile.cooldown(RECRUIT_EXTRA_COOLDOWN_SECONDS, profile.eco.recruit_cooldown))
    if not acquired:
        ttl = await redis.ttl(key)
        raise RecruitOnCooldownError(retry_after_seconds=max(0, ttl))

    eco = profile.eco
    rank = roll_extra_rank(phase, await get_influence(session, user_id), eco.recruit_rank_bonus)
    # Шанс завербовать сразу двоих (Джинчоль, гений харизмы) — второй того же ранга.
    count = 2 if eco.recruit_double and random() < min(0.9, eco.recruit_double) else 1
    for _ in range(count):
        await recruit_into_stack(session, user_id, rank)
    await quest_event(session, user_id, TASK_RECRUIT, count)
    await session.commit()
    return RecruitResult(rank=rank, power=extra_power_for_rank(rank))
