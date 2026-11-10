"""Мастерство — цепочка «Преодоление стены», бой с Томом Ли, тренер, очки мастерства (сервис).

Описано пользователем 2026-09-30 + AskUserQuestion (см. `config/mastery`):

1. Все четыре характеристики дошли до EXR → этап 1 назначается на случайный момент 1–24 ч
   (`pending`); пришло время — фоновый проход (`activate_due`) или заход на экран
   активирует его (`active`) и снимает мощь Тома = 80/100/120% лагеря атаки игрока.
2. Задания этапа: этап 1 — победить Тома; этап 2 — 10 личных тренировок, потом Том; этап 3 —
   3 PvP-победы нападающим и победа над игроком ±10% мощи, потом Том. Том открывается, когда
   выполнены все остальные задания этапа.
3. Победил Тома → `trainer`: сразу выдаются 4 очка этапа (2026-11-10: покупка у тренера убрана).
4. Очко вкладывается в любое мастерство до 3 уровня, в любом порядке (можно 3 в силу сразу).
   Вложены все 4 — «прорыв» перед следующим этапом (`QUEST_BREAKTHROUGH`), потом ожидание
   задания; после третьего — цепочка пройдена.

Сам бой с Томом — `services/district/tom.py` (все бои живут в домене district); здесь —
только состояние цепочки (`lock_quest_for_tom`, `mark_tom_defeated`).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.mastery import (
    EQUAL_WIN_POWER_PERCENT,
    MASTERY_LEVEL_CAP,
    MASTERY_POINTS_PER_STAGE,
    MASTERY_BREAKTHROUGH_NEED,
    MASTERY_STAGES,
    MASTERY_SWEEP_BATCH,
    MASTERY_UNLOCK_RANK_INDEX,
    STAGE_TASKS,
    TOM_POWER_MIN,
    TOM_POWER_PERCENT,
    mastery_delay_range_hours,
)
from bot.constant.characteristic import MASTERIES
from bot.constant.mastery import (
    BT_AWAKEN,
    BT_PATH,
    BT_PHASE,
    BT_TECH10,
    QUEST_ACTIVE,
    QUEST_BREAKTHROUGH,
    QUEST_COMPLETE,
    QUEST_PENDING,
    QUEST_TRAINER,
    TASK_EQUAL_WIN,
    TASK_EXTRAS,
    TASK_PVP_WINS,
    TASK_TOM,
    TASK_TRAININGS,
)
from bot.db.models.mastery_quest import MasteryQuest
from bot.db.repositories import characteristic as char_repo
from bot.db.repositories import mastery as mastery_repo
from bot.services.build import capped, get_build
from bot.services.characteristic.combat import get_combat_profile
from bot.services.extra import get_army_stats


class QuestNotActiveError(Exception):
    pass


class TomLockedError(Exception):
    """Том ещё не открыт — сначала остальные задания этапа."""


class NoFreePointsError(Exception):
    pass


class MasteryCappedError(Exception):
    """Это мастерство уже на 3 уровне — вкладывай в другое."""


class QuestBusyError(Exception):
    """Админ: задание этапа уже идёт (или цепочка пройдена)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _random_delay(reduction: float = 0.0, potential: str | None = None, stage: int = 1) -> timedelta:
    """Случайный момент задания этапа — диапазон по потенциалу и этапу
    (`config/mastery.mastery_delay_range_hours`); `reduction` — сокращение от систем развития
    (Самдак: «быстрее получает доступ к заданиям мастерства»), не больше 70%."""
    lo, hi = mastery_delay_range_hours(potential, stage)
    seconds = random.uniform(lo * 3600, hi * 3600)
    return timedelta(seconds=seconds * (1 - capped(reduction, 0.7)))


async def _delay_for(session: AsyncSession, user_id: int, stage: int) -> timedelta:
    from sqlalchemy import select

    from bot.db.models.user import User

    potential = await session.scalar(select(User.potential).where(User.id == user_id))
    return _random_delay(await _delay_reduction(session, user_id), potential, stage)


# --- прорывы перед этапами 2 и 3 ---


async def breakthrough_state(session: AsyncSession, user_id: int) -> dict[str, bool]:
    """Какие «грандиозные» достижения уже есть — одним запросом."""
    from sqlalchemy import text

    from bot.config.development import MAX_LEVEL
    from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST
    from bot.constant.unique_path import PATH_STAGE_OWNED

    row = (await session.execute(text(
        "SELECT u.path_stage, u.awakening_level, u.phase, "
        "EXISTS(SELECT 1 FROM user_techniques t WHERE t.user_id = u.id AND t.level >= :max) "
        "FROM users u WHERE u.id = :u"
    ), {"u": user_id, "max": MAX_LEVEL})).one()
    return {
        BT_PATH: row[0] >= PATH_STAGE_OWNED,
        BT_TECH10: bool(row[3]),
        BT_AWAKEN: row[1] >= 1,
        BT_PHASE: row[2] in (PHASE_CIRCLE, PHASE_FIST),
    }


async def _try_breakthrough(session: AsyncSession, user_id: int, quest: MasteryQuest) -> bool:
    """Прорыв сделан → пошло ожидание задания этапа. НЕ коммитит. → перешёл ли в pending."""
    if quest.status != QUEST_BREAKTHROUGH:
        return False
    state = await breakthrough_state(session, user_id)
    if sum(state.values()) < MASTERY_BREAKTHROUGH_NEED.get(quest.stage, 1):
        return False
    quest.status = QUEST_PENDING
    quest.available_at = _now() + await _delay_for(session, user_id, quest.stage)
    return True


async def check_breakthroughs(session_factory: async_sessionmaker[AsyncSession]) -> list[tuple[int, int]]:
    """Фоновый проход: у кого прорыв уже сделан — запустить ожидание задания.
    → (user_id, этап) — им пуш «стена пробита, ожидайте задание»."""
    async with session_factory() as session:
        ids = await mastery_repo.list_breakthrough(session, MASTERY_SWEEP_BATCH)
    moved = []
    for user_id in ids:
        async with session_factory() as session:
            quest = await mastery_repo.get(session, user_id, for_update=True)
            if quest is not None and await _try_breakthrough(session, user_id, quest):
                await session.commit()
                moved.append((user_id, quest.stage))
    return moved


async def _delay_reduction(session: AsyncSession, user_id: int) -> float:
    return (await get_build(session, user_id)).eco.mastery_delay


# --- задания ---


@dataclass(frozen=True, slots=True)
class TaskView:
    code: str
    target: int
    progress: int
    locked: bool  # Том ещё закрыт

    @property
    def done(self) -> bool:
        return self.progress >= self.target


def _progress(quest: MasteryQuest, code: str) -> int:
    if code == TASK_TRAININGS:
        return quest.progress_trainings
    if code == TASK_EXTRAS:
        return quest.progress_extras
    if code == TASK_PVP_WINS:
        return quest.progress_pvp_wins
    if code == TASK_EQUAL_WIN:
        return int(quest.equal_win)
    return int(quest.status in (QUEST_TRAINER, QUEST_COMPLETE))  # TASK_TOM


def _tasks(quest: MasteryQuest) -> list[TaskView]:
    others_done = all(
        _progress(quest, code) >= target for code, target in STAGE_TASKS[quest.stage] if code != TASK_TOM
    )
    return [
        TaskView(code=code, target=target, progress=min(target, _progress(quest, code)), locked=code == TASK_TOM and not others_done)
        for code, target in STAGE_TASKS[quest.stage]
    ]


def _tom_unlocked(quest: MasteryQuest) -> bool:
    return quest.status == QUEST_ACTIVE and not any(t.locked for t in _tasks(quest) if t.code == TASK_TOM)


# --- открытие и активация этапа ---


async def check_unlock(session: AsyncSession, user_id: int) -> bool:
    """Все четыре характеристики ≥ CX и цепочки ещё нет → назначает этап 1 на случайный
    момент 1–24 ч. Коммитит, если назначила. Вызывается после вложения очков развития."""
    row = await char_repo.get_stats(session, user_id)
    if row is None or min(row.ranks.values()) < MASTERY_UNLOCK_RANK_INDEX:
        return False
    if not await mastery_repo.create_pending(session, user_id, _now() + await _delay_for(session, user_id, 1)):
        return False
    await session.commit()
    return True


async def _activate(session: AsyncSession, user_id: int, stage: int) -> bool:
    """`pending → active` со снимком мощи Тома от текущего лагеря атаки. НЕ коммитит."""
    attack_power = (await get_army_stats(session, user_id)).attack.power
    tom_power = max(TOM_POWER_MIN, attack_power * TOM_POWER_PERCENT[stage] // 100)
    return await mastery_repo.activate(session, user_id, tom_power)


async def activate_due(session_factory: async_sessionmaker[AsyncSession]) -> list[tuple[int, int]]:
    """Фоновый проход: активирует наступившие этапы. Каждый — своя транзакция. Возвращает
    (user_id, этап) тех, кого нужно уведомить."""
    async with session_factory() as session:
        due = await mastery_repo.list_due_pending(session, MASTERY_SWEEP_BATCH)
    activated = []
    for user_id in due:
        async with session_factory() as session:
            quest = await mastery_repo.get(session, user_id, for_update=True)
            if quest is not None and await _activate(session, user_id, quest.stage):
                await session.commit()
                activated.append((user_id, quest.stage))
    return activated


# --- экран ---


@dataclass(frozen=True, slots=True)
class MasteryView:
    mastery: dict[str, int]
    status: str | None  # None — цепочка ещё не открыта
    stage: int
    tasks: list[TaskView]
    tom_power: int
    tom_unlocked: bool
    points_bought: int
    points_free: int
    available_in_seconds: int | None
    breakthrough: dict[str, bool] | None = None  # статус QUEST_BREAKTHROUGH — что уже сделано
    breakthrough_need: int = 0


async def get_view(session: AsyncSession, user_id: int) -> MasteryView:
    mastery = (await get_combat_profile(session, user_id)).mastery
    quest = await mastery_repo.get(session, user_id)
    if quest is None and await check_unlock(session, user_id):
        # Порог открытия снизили (EXR → CX, 2026-10-28) — тем, кто уже дорос, этап назначаем при
        # заходе на экран, не дожидаясь следующего вложения очков развития.
        quest = await mastery_repo.get(session, user_id)
    if quest is not None and quest.status == QUEST_BREAKTHROUGH:
        quest = await mastery_repo.get(session, user_id, for_update=True)
        if await _try_breakthrough(session, user_id, quest):
            await session.commit()
        quest = await mastery_repo.get(session, user_id)
    if quest is not None and quest.status == QUEST_PENDING and quest.available_at <= _now():
        # Ленивая активация — не ждём фонового прохода, если игрок сам открыл экран.
        quest = await mastery_repo.get(session, user_id, for_update=True)
        if await _activate(session, user_id, quest.stage):
            await session.commit()
        quest = await mastery_repo.get(session, user_id)
    if quest is None:
        return MasteryView(mastery, None, 0, [], 0, False, 0, 0, None)
    in_progress = quest.status in (QUEST_ACTIVE, QUEST_TRAINER)
    return MasteryView(
        mastery=mastery,
        status=quest.status,
        stage=quest.stage,
        tasks=_tasks(quest) if in_progress else [],
        tom_power=quest.tom_power,
        tom_unlocked=_tom_unlocked(quest),
        points_bought=quest.points_bought,
        points_free=quest.points_free,
        available_in_seconds=(
            max(0, int((quest.available_at - _now()).total_seconds())) if quest.status == QUEST_PENDING else None
        ),
        breakthrough=await breakthrough_state(session, user_id) if quest.status == QUEST_BREAKTHROUGH else None,
        breakthrough_need=MASTERY_BREAKTHROUGH_NEED.get(quest.stage, 0) if quest.status == QUEST_BREAKTHROUGH else 0,
    )


# --- прогресс заданий (хуки из других доменов, НЕ коммитят) ---


async def record_training(session: AsyncSession, user_id: int) -> None:
    """Личная тренировка засчитывается в задание любого этапа."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is not None and quest.status == QUEST_ACTIVE:
        quest.progress_trainings += 1


async def record_extras_training(session: AsyncSession, user_id: int) -> None:
    """Тренировка статистов засчитывается в задание любого этапа."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is not None and quest.status == QUEST_ACTIVE:
        quest.progress_extras += 1


async def record_pvp_win(session: AsyncSession, user_id: int, own_power: int, enemy_power: int) -> None:
    """Победа нападающим в PvP-вызове → задание этапа 3; если мощь противника в бою в
    пределах ±10% от своей — ещё и «победа над равным»."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is None or quest.status != QUEST_ACTIVE or quest.stage != 3:
        return
    quest.progress_pvp_wins += 1
    if own_power > 0 and abs(enemy_power - own_power) * 100 <= own_power * EQUAL_WIN_POWER_PERCENT:
        quest.equal_win = True


# --- бой с Томом (сам бой — `services/district/tom.py`, здесь только состояние цепочки) ---


async def lock_quest_for_tom(session: AsyncSession, user_id: int) -> MasteryQuest:
    """Строка цепочки под `FOR UPDATE` для боя с Томом: этап активен и Том открыт."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is None or quest.status != QUEST_ACTIVE:
        raise QuestNotActiveError
    if not _tom_unlocked(quest):
        raise TomLockedError
    return quest


def mark_tom_defeated(quest: MasteryQuest) -> None:
    """Том побеждён → сразу 4 очка этапа (покупка у тренера убрана 2026-11-10). НЕ коммитит."""
    _grant_stage_points(quest)


def _grant_stage_points(quest: MasteryQuest) -> None:
    """Задания этапа закрыты: `trainer` + 4 очка. Повторно этап не выдаёт (`points_bought`)."""
    quest.status = QUEST_TRAINER
    quest.points_free += max(0, MASTERY_POINTS_PER_STAGE - quest.points_bought)
    quest.points_bought = MASTERY_POINTS_PER_STAGE


# --- очки ---


@dataclass(frozen=True, slots=True)
class InvestResult:
    mastery: str
    new_tier: int
    stage_finished: bool
    chain_complete: bool
    waiting: bool = False  # прорыв уже сделан — задание следующего этапа в пути


async def invest_point(session: AsyncSession, user_id: int, mastery: str) -> InvestResult:
    """Вкладывает очко в мастерство (до 3 уровня, в любом порядке). Вложены все 4 очка этапа →
    этап закрыт: прорыв перед следующим, после третьего — цепочка пройдена. Коммитит."""
    if mastery not in MASTERIES:
        raise MasteryCappedError
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is None or quest.points_free <= 0:
        raise NoFreePointsError
    if not await mastery_repo.bump_mastery(session, user_id, mastery, cap=MASTERY_LEVEL_CAP):
        raise MasteryCappedError
    quest.points_free -= 1
    stage_finished = quest.points_bought >= MASTERY_POINTS_PER_STAGE and quest.points_free == 0
    chain_complete = False
    if stage_finished:
        if quest.stage >= MASTERY_STAGES:
            quest.status = QUEST_COMPLETE
            chain_complete = True
        else:
            # Перед следующим этапом — «прорыв» (пользователь 2026-10-28): ожидание задания
            # начнётся, только когда игрок сделает что-то грандиозное (`_try_breakthrough`).
            quest.stage += 1
            quest.status = QUEST_BREAKTHROUGH
            quest.available_at = _now()
            quest.tom_power = 0
            quest.progress_trainings = quest.progress_pvp_wins = quest.progress_extras = 0
            quest.equal_win = False
            quest.points_bought = 0
            # Достижения прорыва могут быть уже сделаны — тогда ожидание задания стартует сразу.
            await _try_breakthrough(session, user_id, quest)
    await session.commit()
    new_tier = (await get_combat_profile(session, user_id)).mastery[mastery]
    return InvestResult(mastery, new_tier, stage_finished, chain_complete, quest.status == QUEST_PENDING)


# --- админ (2026-11-10: «выдать квест, скипнуть квест, выдать очки мастерства») ---


async def admin_give_quest(session: AsyncSession, user_id: int) -> int:
    """Задание этапа — прямо сейчас: без ожидания и без прорыва. Нет цепочки — открывает этап 1.
    Коммитит. → этап."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is None:
        await mastery_repo.create_pending(session, user_id, _now() - timedelta(minutes=5))
        quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest.status not in (QUEST_PENDING, QUEST_BREAKTHROUGH):
        raise QuestBusyError
    quest.status = QUEST_PENDING
    # С запасом в прошлое: активация сверяет с now() начала транзакции, а не с часами Python.
    quest.available_at = _now() - timedelta(minutes=5)
    await session.flush()
    await _activate(session, user_id, quest.stage)
    await session.commit()
    return quest.stage


async def admin_skip_stage(session: AsyncSession, user_id: int) -> int:
    """Засчитать задания текущего этапа и Тома: сразу 4 очка. Этап ещё не пришёл — сначала
    выдаёт его. Коммитит. → этап."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is None or quest.status in (QUEST_PENDING, QUEST_BREAKTHROUGH):
        await admin_give_quest(session, user_id)
        quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest.status != QUEST_ACTIVE:
        raise QuestBusyError
    _grant_stage_points(quest)
    await session.commit()
    return quest.stage


async def admin_give_points(session: AsyncSession, user_id: int, amount: int) -> int:
    """± невложенные очки мастерства (не ниже 0). Нет цепочки — заводит её с этапа 1 (задание
    придёт сразу), чтобы очкам было где лежать и цепочка не считалась пройденной. Коммитит."""
    quest = await mastery_repo.get(session, user_id, for_update=True)
    if quest is None:
        await mastery_repo.create_pending(session, user_id, _now())
        quest = await mastery_repo.get(session, user_id, for_update=True)
    quest.points_free = max(0, quest.points_free + amount)
    await session.commit()
    return quest.points_free
