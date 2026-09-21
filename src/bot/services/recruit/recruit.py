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
from random import randint

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import recruit_extra_cooldown
from bot.config.characteristic import extra_power_for_rank
from bot.config.game import INFLUENCE_STARTING, RECRUIT_EXTRA_COOLDOWN_SECONDS
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG
from bot.services.extra import recruit_into_stack

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


def get_influence() -> int:
    """Пока всегда стартовое значение — «влияние растёт от захваченных районов/городов»
    (raw-notes), а захват территории ещё не реализован (домен `district`). Как только
    он появится, здесь будет реальный подсчёт по владению, не константа."""
    return INFLUENCE_STARTING


def roll_extra_rank(phase: str) -> str:
    ceiling_index = min(PHASE_RANK_CAP_INDEX[phase], get_influence())
    return RANK_LADDER[randint(0, ceiling_index)]


async def recruit_extra(session: AsyncSession, redis: Redis, user_id: int, phase: str) -> RecruitResult:
    """Атомарный `SET NX EX` — сам ключ и есть КД (правило 4, см. `cache/keys.
    recruit_extra_cooldown`): если он не взят, вербовка недоступна ещё
    `retry_after_seconds`. Единственный шаг после — +1 к стопке (ранг, 0, 0),
    коммитит здесь один раз (правило 10 — это top-level операция, не композируется
    ни с чем ещё)."""
    key = recruit_extra_cooldown(user_id)
    acquired = await redis.set(key, "1", nx=True, ex=RECRUIT_EXTRA_COOLDOWN_SECONDS)
    if not acquired:
        ttl = await redis.ttl(key)
        raise RecruitOnCooldownError(retry_after_seconds=max(0, ttl))

    rank = roll_extra_rank(phase)
    await recruit_into_stack(session, user_id, rank)
    await session.commit()
    return RecruitResult(rank=rank, power=extra_power_for_rank(rank))
