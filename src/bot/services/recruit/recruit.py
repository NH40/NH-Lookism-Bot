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

from bot.services.admin.live_config import cooldown_seconds
from bot.constant.admin.live_config import KEY_CD_RECRUIT
from bot.cache.keys import recruit_extra_cooldown
from bot.config.characteristic import extra_power_for_rank
from bot.config.game import RECRUIT_SELECT_DIVISOR, RECRUIT_SELECT_FLOOR, influence_rank_index, recruit_quantity
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG
from bot.constant.dev_quest import TASK_RECRUIT
from bot.services.dev_quest import emit as quest_event
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
    rank: str  # лучший ранг партии
    power: int
    count: int = 1
    by_rank: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class RecruitOffer:
    """Что даст вербовка сейчас: бойцов за нажатие в обычном режиме и в отборе, потолок ранга."""

    crowd: int
    select: int
    ceiling: str
    influence: int


def recruit_ceiling_rank(phase: str, influence: int, cut: float = 0.0) -> str:
    """Лучший ранг, который вообще может выпасть при вербовке: min(потолок фазы, влияние)."""
    return RANK_LADDER[min(PHASE_RANK_CAP_INDEX[phase], influence_rank_index(influence, cut))]


def roll_extra_rank(phase: str, influence: int, rank_bonus: int = 0, cut: float = 0.0, floor: float = 0.0) -> str:
    """Влияние считается от захваченных районов (`services/district.get_influence`, +1 за
    район) — каждый захваченный район поднимает потолок вербовки на одну ступень.
    `rank_bonus` — ступени сверх потолка от систем развития (Джинчоль, гений войны):
    поднимает и потолок влияния, и потолок фазы — «военные вербуют лучше»."""
    ceiling_index = min(PHASE_RANK_CAP_INDEX[phase] + rank_bonus, influence_rank_index(influence, cut) + rank_bonus, len(RANK_LADDER) - 1)
    return RANK_LADDER[randint(int(ceiling_index * floor), ceiling_index)]


def _crowd_size(eco, influence: int) -> int:
    return recruit_quantity(
        influence, cut=eco.recruit_influence_cut, quantity=eco.recruit_quantity, cap=eco.recruit_cap
    )


def _rank_cut(eco) -> float:
    return eco.recruit_influence_cut + eco.influence_rank_cut


async def get_offer(session: AsyncSession, user_id: int, phase: str) -> RecruitOffer:
    profile = await get_combat_profile(session, user_id)
    eco, influence = profile.eco, profile.build.influence
    crowd = _crowd_size(eco, influence)
    ceiling = min(
        PHASE_RANK_CAP_INDEX[phase] + eco.recruit_rank_bonus,
        influence_rank_index(influence, _rank_cut(eco)) + eco.recruit_rank_bonus,
        len(RANK_LADDER) - 1,
    )
    return RecruitOffer(crowd=crowd, select=max(1, crowd // RECRUIT_SELECT_DIVISOR), ceiling=RANK_LADDER[ceiling], influence=influence)


async def recruit_extra(session: AsyncSession, redis: Redis, user_id: int, phase: str, *, select: bool = False) -> RecruitResult:
    """Атомарный `SET NX EX` — сам ключ и есть КД (правило 4, см. `cache/keys.
    recruit_extra_cooldown`): если он не взят, вербовка недоступна ещё
    `retry_after_seconds`. Единственный шаг после — +1 к стопке (ранг, 0, 0),
    коммитит здесь один раз (правило 10 — это top-level операция, не композируется
    ни с чем ещё).

    Бойцов за нажатие решает влияние (`config/game.recruit_quantity`), у каждого свой случайный ранг —
    одним биномиальным проходом, а не циклом по бойцам: партия у Ким Гапрена — сотни. `select` — отбор:
    вчетверо меньше бойцов, зато ранг только из верхней половины доступных."""
    key = recruit_extra_cooldown(user_id)
    profile = await get_combat_profile(session, user_id)
    acquired = await redis.set(key, "1", nx=True, ex=profile.cooldown(cooldown_seconds(KEY_CD_RECRUIT), profile.eco.recruit_cooldown))
    if not acquired:
        ttl = await redis.ttl(key)
        raise RecruitOnCooldownError(retry_after_seconds=max(0, ttl))

    eco = profile.eco
    influence = profile.build.influence
    count = _crowd_size(eco, influence)
    if select:
        count = max(1, count // RECRUIT_SELECT_DIVISOR)
    # Шанс завербовать вдвое больше (гений харизмы).
    if eco.recruit_double and random() < min(0.9, eco.recruit_double):
        count *= 2
    floor = RECRUIT_SELECT_FLOOR if select else 0.0
    ranks: dict[str, int] = {}
    for _ in range(count):
        rank = roll_extra_rank(phase, influence, eco.recruit_rank_bonus, _rank_cut(eco), floor)
        ranks[rank] = ranks.get(rank, 0) + 1
    for rank in sorted(ranks, key=RANK_INDEX.__getitem__):  # один порядок блокировок стопок
        await recruit_into_stack(session, user_id, rank, ranks[rank])
    await quest_event(session, user_id, TASK_RECRUIT, count)
    await session.commit()
    best = max(ranks, key=RANK_INDEX.__getitem__)
    by_rank = tuple(sorted(ranks.items(), key=lambda kv: -RANK_INDEX[kv[0]]))
    return RecruitResult(rank=best, power=extra_power_for_rank(best), count=count, by_rank=by_rank)
