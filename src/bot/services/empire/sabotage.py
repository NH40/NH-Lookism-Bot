"""Саботаж снизу против императора — кража статистов, переманивание уника, кража из казны.

Пользователь 2026-10-01 (`docs/design/fist_emperor.md` + AskUserQuestion):
- банды и круги страны крадут у своего императора, чтобы отбить часть того, что он забирает;
- исход — **фиксированный шанс** на каждое действие (мощь не влияет), без боя и потерь;
- провал — **только КД** (большой, общий на все действия); император получает пуш «кто-то
  пытался», без имени;
- переманить можно только уника, **не стоящего на позиции** (копии на позициях лежат в
  `card_positions`, а не в `card_stacks` — значит, «свободные копии» = стопки армии);
- раскрытие саботажника — будущий навык Шпиона на позиции; журнал `sabotage_logs` хранит
  саботажника именно для него.

Числа (шансы, доли, потолки, КД) — решение автора кода (`config/empire`).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.absolute import ABSOLUTES
from bot.cache.keys import sabotage_cooldown
from bot.config.empire import (
    SABOTAGE_CHANCE_PERCENT,
    SABOTAGE_COOLDOWN_SECONDS,
    SABOTAGE_STATISTS_FLOOR,
    SABOTAGE_STATISTS_PERCENT,
    SABOTAGE_TREASURY_CAP,
    SABOTAGE_TREASURY_PERCENT,
)
from bot.constant.empire import SABOTAGE_ACTIONS, SABOTAGE_STATISTS, SABOTAGE_TREASURY, SABOTAGE_UNIQUE
from bot.constant.extra import CAMP_ATTACK
from bot.db.repositories import card as card_repo
from bot.db.repositories import empire as empire_repo
from bot.db.repositories import extra as extra_repo
from bot.db.repositories.empire import TaxContext
from bot.db.repositories.activity import list_marks
from bot.services.build import get_build
from bot.services.characteristic import get_combat_profile


class NoEmperorError(Exception):
    """У города игрока нет императора (или игрок сам император)."""


class UnknownSabotageError(Exception):
    pass


class NothingToStealError(Exception):
    """У императора нечего красть этим действием — попытка не тратит КД."""


class SabotageOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class SabotageView:
    emperor: TaxContext
    cooldowns: dict[str, int]  # действие → секунд до попытки (0 — можно)


@dataclass(frozen=True, slots=True)
class SabotageResult:
    action: str
    success: bool
    emperor_id: int
    amount: int = 0  # статистов / NHCoin / 1 уник
    silent: bool = False  # император не получает пуша (Курода)
    rank: str | None = None  # ранг украденной стопки статистов
    card_code: str | None = None


async def get_view(session: AsyncSession, redis: Redis, user_id: int) -> SabotageView:
    emperor = await empire_repo.get_tax_context(session, user_id)
    if emperor is None:
        raise NoEmperorError
    ttls = [await redis.ttl(sabotage_cooldown(user_id, action)) for action in SABOTAGE_ACTIONS]
    return SabotageView(emperor=emperor, cooldowns={a: max(0, t) for a, t in zip(SABOTAGE_ACTIONS, ttls)})


async def _steal_statists(session: AsyncSession, emperor_id: int, user_id: int, rng: random.Random, loot: float = 0.0) -> SabotageResult:
    stacks = await extra_repo.list_stacks(session, emperor_id, for_update=True)
    if not stacks:  # успели потратить между проверкой и кражей
        raise NothingToStealError
    stack = rng.choice(stacks)
    cap = max(await extra_repo.total_quantity(session, user_id), SABOTAGE_STATISTS_FLOOR)
    amount = min(max(int(stack.quantity * SABOTAGE_STATISTS_PERCENT / 100 * (1 + loot)), 1), int(cap * (1 + loot)), stack.quantity)
    key = {
        "rank": stack.rank, "stars": stack.stars, "training_level": stack.training_level,
        "school": stack.school, "school_level": stack.school_level,
    }
    await extra_repo.add_to_stack(session, user_id=emperor_id, camp=stack.camp, quantity=-amount, **key)
    await extra_repo.add_to_stack(session, user_id=user_id, camp=CAMP_ATTACK, quantity=amount, **key)
    return SabotageResult(SABOTAGE_STATISTS, True, emperor_id, amount=amount, rank=stack.rank)


async def _lure_unique(session: AsyncSession, emperor_id: int, user_id: int, rng: random.Random, loot: float = 0.0) -> SabotageResult:
    stacks = [s for s in await card_repo.list_stacks(session, emperor_id, for_update=True) if s.card_code not in ABSOLUTES]
    if not stacks:
        raise NothingToStealError
    # Взвешенно по числу копий: чем больше у императора копий карты, тем вероятнее уйдёт она.
    stack = rng.choices(stacks, weights=[s.quantity for s in stacks])[0]
    await card_repo.add_to_stack(session, user_id=emperor_id, card_code=stack.card_code, camp=stack.camp, quantity=-1)
    await card_repo.add_to_stack(session, user_id=user_id, card_code=stack.card_code, camp=CAMP_ATTACK, quantity=1)
    return SabotageResult(SABOTAGE_UNIQUE, True, emperor_id, amount=1, card_code=stack.card_code)


async def _steal_treasury(session: AsyncSession, emperor_id: int, user_id: int, rng: random.Random, loot: float = 0.0) -> SabotageResult:
    coins = await empire_repo.emperor_coins(session, emperor_id, for_update=True)
    if coins <= 0:
        raise NothingToStealError
    amount = min(max(int(coins * SABOTAGE_TREASURY_PERCENT / 100 * (1 + loot)), 1), int(SABOTAGE_TREASURY_CAP * (1 + loot)), coins)
    await empire_repo.move_coins(session, emperor_id, user_id, amount)
    return SabotageResult(SABOTAGE_TREASURY, True, emperor_id, amount=amount)


_STEAL = {
    SABOTAGE_STATISTS: _steal_statists,
    SABOTAGE_UNIQUE: _lure_unique,
    SABOTAGE_TREASURY: _steal_treasury,
}


async def _has_target(session: AsyncSession, action: str, emperor_id: int) -> bool:
    if action == SABOTAGE_STATISTS:
        return bool(await extra_repo.list_stacks(session, emperor_id))
    if action == SABOTAGE_UNIQUE:
        return any(c.card_code not in ABSOLUTES for c in await card_repo.list_stacks(session, emperor_id))
    return await empire_repo.emperor_coins(session, emperor_id) > 0


class NotMarkedTargetError(Exception):
    """Саботаж игрока без метки или без способности «саботаж помеченных» (путь Сенсорики)."""


async def _target(session: AsyncSession, user_id: int, target_id: int | None) -> TaxContext:
    """Цель саботажа: император своего города (по умолчанию) или помеченный игрок — путь
    Сенсорики, пользователь: «метки на игроков… устраивать саботажи у этих игроков»."""
    if target_id is None:
        emperor = await empire_repo.get_tax_context(session, user_id)
        if emperor is None:
            raise NoEmperorError
        return emperor
    build = await get_build(session, user_id)
    if "sabotage_marked" not in build.flags or target_id not in await list_marks(session, user_id):
        raise NotMarkedTargetError
    return TaxContext(emperor_id=target_id, percent=0, emperor_username=None, emperor_name=None)


async def sabotage(
    session: AsyncSession,
    redis: Redis,
    user_id: int,
    action: str,
    *,
    rng: random.Random | None = None,
    target_id: int | None = None,
) -> SabotageResult:
    """Одна попытка. КД — `SET NX EX` (правило 4, ключ и есть КД, он же защита от двойного
    клика — правило 2). Кража — под `FOR UPDATE` строк императора, коммит один раз в конце
    (правило 10); при неожиданной ошибке после взятия КД он снимается — попытка не сгорает
    из-за сбоя."""
    if action not in SABOTAGE_ACTIONS:
        raise UnknownSabotageError(action)
    rng = rng or random.Random()
    emperor = await _target(session, user_id, target_id)
    key = sabotage_cooldown(user_id, action)
    # Сначала КД (игроку на перерыве важнее таймер), потом цель: «нечего красть» сообщаем
    # до взятия КД — тратить попытку на заведомо пустую цель нечестно. Сама гарантия
    # «одна попытка» — атомарный SET NX ниже, это чтение — только порядок сообщений.
    ttl = await redis.ttl(key)
    if ttl > 0:
        raise SabotageOnCooldownError(retry_after_seconds=ttl)
    if not await _has_target(session, action, emperor.emperor_id):
        raise NothingToStealError

    profile = await get_combat_profile(session, user_id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(SABOTAGE_COOLDOWN_SECONDS, profile.eco.sabotage_cooldown)):
        raise SabotageOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))
    try:
        eco = profile.eco
        # Бафы систем развития (Курода, гений хакинга): +шанс (не выше 90%) и +добыча.
        chance = min(90.0, SABOTAGE_CHANCE_PERCENT[action] + eco.sabotage_chance * 100)
        # Безопасность цели: «Чистые ряды» (любой саботаж) и «Аудит» Бизнесмена (кража казны).
        target_pos = (await get_build(session, emperor.emperor_id)).positions
        if target_pos is not None:
            chance -= target_pos.get("anti_sabotage") * 100
            if action == SABOTAGE_TREASURY:
                chance -= target_pos.get("anti_treasury_theft") * 100
        if rng.random() * 100 < chance:
            result = await _STEAL[action](session, emperor.emperor_id, user_id, rng, eco.sabotage_loot)
        else:
            result = SabotageResult(action, False, emperor.emperor_id)
        if eco.silent_sabotage:
            result = replace(result, silent=True)
        await empire_repo.add_sabotage_log(
            session, emperor_id=emperor.emperor_id, saboteur_id=user_id, action=action,
            success=result.success, amount=result.amount, card_code=result.card_code,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return result
