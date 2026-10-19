"""Путь (сервис). Дизайн — `docs/design/development_systems.md`, «Путь».

Стадии (`users.path_stage`, пользователь 2026-10-02):
0 → 1: сумма рангов характеристик дошла до порога по потенциалу — приходит
       «подтверждение убеждений» (квест убеждения);
1 → 2: квест выполнен — у игрока появилось **убеждение**, дальше копит фрагменты пути
       (с босса Ким Гапрена);
2 → 3: собрал `PATH_AWAKEN_FRAGMENTS` — «Пробудить путь»: **путь выпадает случайно**
       (1 уровень, сразу активен). Пользователь 2026-10-04: фрагменты нужны только для этого.
Дальше уровни — за **очки пути**, которые даются за активность (`dev_quest.award_path_points`,
`config/unique_path.PATH_POINT_SOURCES`), а не за фрагменты. Путь держится до сброса
прогресса (удаление банды, пробуждение — их правила стирают `user_paths` и стадию).
Несколько путей (донат, позже) переключаются не чаще `PATH_SWAP_COOLDOWN_SECONDS`.
"""
from __future__ import annotations

from bot.services.admin.live_config import cooldown_seconds
from bot.constant.admin.live_config import KEY_CD_SWAP_PATH
from bot.constant.donate import KIND_PATH
from bot.db.repositories import donate as donate_repo

from bot.services.dev_quest import emit as quest_event

import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import swap_cooldown
from bot.config.development import MAX_LEVEL
from bot.config.unique_path import (
    CONVICTION_QUEST,
    CONVICTION_RANK_SUM,
    PATH_AWAKEN_FRAGMENTS,
    path_level_cost,
)
from bot.constant.activity import ACT_DEVELOPMENT
from bot.constant.dev_quest import QUEST_CONVICTION, TASK_DEV_LEVEL
from bot.constant.unique_path import PATH_SOURCE_DAILY
from bot.constant.unique_path import (
    PATH_STAGE_CALLED,
    PATH_STAGE_CONVICTION,
    PATH_STAGE_NONE,
    PATH_STAGE_OWNED,
    PATHS,
)
from bot.db.repositories import unique_path as path_repo
from bot.services.activity import log as log_activity
from bot.services.dev_quest import QuestView, award_path_points, claim, list_active, start
from bot.texts.activity import LOG_PATH_LEVEL, LOG_PATH_NEW
from bot.texts.unique_path import PATH_NAMES


class QuestNotCompleteError(Exception):
    pass


class WrongStageError(Exception):
    pass


class PathNotOwnedError(Exception):
    pass


class PathMaxLevelError(Exception):
    pass


class NotEnoughFragmentsError(Exception):
    def __init__(self, cost: int, have: int) -> None:
        super().__init__(cost, have)
        self.cost, self.have = cost, have


class NotEnoughPointsError(Exception):
    def __init__(self, cost: int, have: int) -> None:
        super().__init__(cost, have)
        self.cost, self.have = cost, have


class NoSecondBodyError(Exception):
    pass


class SwapOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class PathView:
    stage: int
    rank_sum: int
    rank_needed: int
    quest: QuestView | None
    active: str | None
    owned: dict[str, int]
    fragments: int
    awaken_cost: int
    points: int
    next_cost: int | None
    swap_cooldown: int
    # Донат: купленные пути (выбор при пробуждении вместо случайного) и второе тело.
    bought: tuple[str, ...] = ()
    second_body: bool = False
    active2: str | None = None
    next_cost2: int | None = None


def _threshold(potential: str | None) -> int:
    return CONVICTION_RANK_SUM.get(potential or "", max(CONVICTION_RANK_SUM.values()))



async def _swap_cd(session: AsyncSession, user_id: int, seconds: int) -> int:
    """КД переключения с мастерством Скорости («−10/20/30% ко ВСЕМ КД», raw-notes; до 2026-10-12
    переключения его не учитывали)."""
    from bot.services.characteristic import get_combat_profile

    return (await get_combat_profile(session, user_id)).cooldown(seconds)

async def check_conviction(session: AsyncSession, user_id: int) -> bool:
    """Пора ли «подтверждение убеждений»: стадия 0 и сумма рангов ≥ порога потенциала →
    стадия 1 и квест убеждения. Коммитит, если сработало. → True — только что пришло."""
    state = await path_repo.get_state(session, user_id)
    if state is None:
        return False
    stage, _, _, potential, ranks = state
    if stage != PATH_STAGE_NONE or sum(ranks.values()) < _threshold(potential):
        return False
    if not await path_repo.advance_stage(session, user_id, PATH_STAGE_NONE, PATH_STAGE_CALLED):
        return False
    await start(session, user_id, QUEST_CONVICTION, "", CONVICTION_QUEST)
    await session.commit()
    return True


async def get_view(session: AsyncSession, redis: Redis, user_id: int) -> PathView:
    stage, active, fragments, potential, ranks = await path_repo.get_state(session, user_id)
    owned = dict(await path_repo.list_owned(session, user_id))
    quest = None
    if stage == PATH_STAGE_CALLED:
        quest = next(iter(await list_active(session, user_id, QUEST_CONVICTION)), None)
    level = owned.get(active, 0)
    body = await donate_repo.body_state(session, user_id)
    second_body, active2 = (bool(body[0]), body[1]) if body else (False, None)
    level2 = owned.get(active2, 0) if second_body and active2 else 0
    bought = tuple(code for (_, code) in await donate_repo.unlocks(session, user_id, KIND_PATH))
    return PathView(
        stage=stage,
        rank_sum=sum(ranks.values()),
        rank_needed=_threshold(potential),
        quest=quest,
        active=active,
        owned=owned,
        fragments=fragments,
        awaken_cost=PATH_AWAKEN_FRAGMENTS,
        points=await path_repo.get_points(session, user_id),
        next_cost=path_level_cost(level + 1) if active and level < MAX_LEVEL else None,
        swap_cooldown=max(0, await redis.ttl(swap_cooldown(user_id, "path"))),
        bought=bought,
        second_body=second_body,
        active2=active2 if second_body else None,
        next_cost2=path_level_cost(level2 + 1) if level2 and level2 < MAX_LEVEL else None,
    )


async def claim_conviction(session: AsyncSession, user_id: int) -> None:
    """Квест убеждения выполнен → убеждение; дальше — копить фрагменты на пробуждение. Коммитит."""
    if await claim(session, user_id, QUEST_CONVICTION) is None:
        raise QuestNotCompleteError
    if not await path_repo.advance_stage(session, user_id, PATH_STAGE_CALLED, PATH_STAGE_CONVICTION):
        await session.rollback()
        raise WrongStageError
    await session.commit()


async def awaken_path(
    session: AsyncSession, user_id: int, rng: random.Random | None = None, choice: str | None = None
) -> str:
    """«Пробудить путь»: списать `PATH_AWAKEN_FRAGMENTS` фрагментов → путь выпадает случайно,
    либо (`choice`) игрок берёт путь, купленный за донат (пользователь 2026-10-08). Списание и
    смена стадии — один условный UPDATE (двойной клик не спишет дважды). Коммитит. → код пути."""
    if choice is not None and not await donate_repo.floor(session, user_id, KIND_PATH, choice):
        raise PathNotOwnedError
    state = await path_repo.get_state(session, user_id)
    if state is None or state[0] != PATH_STAGE_CONVICTION:
        raise WrongStageError
    if not await path_repo.awaken(session, user_id, PATH_STAGE_CONVICTION, PATH_STAGE_OWNED, PATH_AWAKEN_FRAGMENTS):
        fresh = await path_repo.get_state(session, user_id)
        if fresh is None or fresh[0] != PATH_STAGE_CONVICTION:
            raise WrongStageError
        raise NotEnoughFragmentsError(PATH_AWAKEN_FRAGMENTS, fresh[2])
    code = choice or (rng or random).choice(PATHS)
    await grant(session, user_id, code)
    await session.commit()
    return code


async def grant(session: AsyncSession, user_id: int, code: str) -> None:
    """Выдать путь и сделать активным (квест, донат). НЕ коммитит."""
    await path_repo.add(session, user_id, code)
    # Купленный за донат уровень пути — сразу (пол уровня, `services/donate`).
    if level := await donate_repo.floor(session, user_id, KIND_PATH, code):
        await donate_repo.raise_owned_level(session, user_id, KIND_PATH, code, level)
    await path_repo.set_active(session, user_id, code)
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_PATH_NEW.format(name=PATH_NAMES[code]))


async def level_up(session: AsyncSession, user_id: int, slot: int = 1) -> int:
    """+1 уровень активного пути за очки пути; `slot=2` — второй путь (второе тело)."""
    stage, active, *_ = await path_repo.get_state(session, user_id)
    if slot == 2:
        body = await donate_repo.body_state(session, user_id)
        if not body or not body[0]:
            raise NoSecondBodyError
        active = body[1]
    owned = dict(await path_repo.list_owned(session, user_id))
    if not active or active not in owned:
        raise PathNotOwnedError
    current = owned[active]
    if current >= MAX_LEVEL:
        raise PathMaxLevelError
    cost = path_level_cost(current + 1)
    if not await path_repo.spend_points(session, user_id, cost):
        raise NotEnoughPointsError(cost, await path_repo.get_points(session, user_id))
    if not await path_repo.bump_level(session, user_id, active, current):
        await session.rollback()
        raise PathMaxLevelError
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_PATH_LEVEL.format(name=PATH_NAMES[active], level=current + 1))
    await quest_event(session, user_id, TASK_DEV_LEVEL)
    await session.commit()
    return current + 1


async def activate(session: AsyncSession, redis: Redis, user_id: int, code: str) -> None:
    owned = dict(await path_repo.list_owned(session, user_id))
    if code not in owned:
        raise PathNotOwnedError
    key = swap_cooldown(user_id, "path")
    if not await redis.set(key, "1", nx=True, ex=await _swap_cd(session, user_id, cooldown_seconds(KEY_CD_SWAP_PATH))):
        raise SwapOnCooldownError(max(0, await redis.ttl(key)))
    body = await donate_repo.body_state(session, user_id)
    if body and body[1] == code:  # путь был вторым — меняются местами
        state = await path_repo.get_state(session, user_id)
        await donate_repo.set_active_path2(session, user_id, state[1] if state else None)
    await path_repo.set_active(session, user_id, code)
    await session.commit()


async def activate2(session: AsyncSession, redis: Redis, user_id: int, code: str) -> None:
    """Второй активный путь (донат «второе тело»): бафы обоих путей действуют сразу."""
    body = await donate_repo.body_state(session, user_id)
    if not body or not body[0]:
        raise NoSecondBodyError
    owned = dict(await path_repo.list_owned(session, user_id))
    state = await path_repo.get_state(session, user_id)
    if code not in owned or (state and state[1] == code):
        raise PathNotOwnedError
    key = swap_cooldown(user_id, "path2")
    if not await redis.set(key, "1", nx=True, ex=await _swap_cd(session, user_id, cooldown_seconds(KEY_CD_SWAP_PATH))):
        raise SwapOnCooldownError(max(0, await redis.ttl(key)))
    await donate_repo.set_active_path2(session, user_id, code)
    await session.commit()


async def award_daily(session: AsyncSession, user_id: int) -> int | None:
    """Очки пути за ежедневный заход (не чаще интервала источника). Коммитит, если начислено.
    → новый баланс или None."""
    balance = await award_path_points(session, user_id, PATH_SOURCE_DAILY)
    if balance is not None:
        await session.commit()
    return balance
