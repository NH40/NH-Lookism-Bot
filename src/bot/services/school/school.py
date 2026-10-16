"""Учителя статистов и их школы (сервис).

Пользователь 2026-10-03:
- на карте в случайный момент появляется **учитель статистов** (пуш игрокам) — Хансу
  (ловкость), Элита (скорость), Бэкхо (техника), Том Ли (сила);
- встретился — учитель **даёт задание**; выполнил — учитель **появляется в магазине**
  («Обучение»); **купил** — открывается **обучение** у него;
- **каждое занятие тоже стоит денег**, но меньше самого учителя;
- учителя «позволяют статистам выходить в школы и получать бафы».

Занятие: случайная доля статистов (`SCHOOL_COVERAGE_PERCENT`) — новички без школы вступают
в школу учителя (1-й уровень), ученики этой школы поднимают её уровень (до
`SCHOOL_MAX_LEVEL`). Статист — ученик одной школы. Бафы школы — у стопки в бою
(`services/district/army.combat_stacks`). Тренажёрные залы и бафы тренировки систем
развития (`extras_training`, `extras_extra_roll`) помогают и здесь.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.unique_path import bump_training_reps
from bot.cache.keys import action_lock, school_lesson_cooldown
from bot.config.game import ACTION_LOCK_MS
from bot.config.school import (
    SCHOOL_COVERAGE_PERCENT,
    SCHOOL_JOIN_PERCENT,
    SCHOOL_LESSON_COOLDOWN_SECONDS,
    SCHOOL_LESSON_PRICE,
    SCHOOL_LEVEL_UP_PERCENT,
    SCHOOL_MAX_LEVEL,
    SCHOOL_QUESTS,
    SCHOOL_TEACHER_PRICE,
)
from bot.constant.dev_quest import QUEST_SCHOOL, TASK_SCHOOL_LESSON
from bot.constant.event import EVENT_SCHOOL_TEACHER
from bot.constant.school import LOCK_ACTION_SCHOOL, SCHOOL_NONE, SCHOOLS
from bot.db.models.development import UserSchool
from bot.db.repositories import business as business_repo
from bot.db.repositories import event as event_repo
from bot.db.repositories.extra import add_to_stack, list_stacks
from bot.services.business import gym_training_bonus_percent
from bot.services.characteristic import get_combat_profile
from bot.services.dev_quest import QuestView, claim, emit, list_active, start


class TeacherGoneError(Exception):
    pass


class UnknownSchoolError(Exception):
    pass


class AlreadyUnlockedError(Exception):
    """Учитель уже в магазине (или куплен) — задание не нужно."""


class QuestAlreadyActiveError(Exception):
    pass


class QuestNotCompleteError(Exception):
    pass


class TeacherNotUnlockedError(Exception):
    """Учителя нет в магазине — сначала встреть его на карте и выполни задание."""


class TeacherAlreadyOwnedError(Exception):
    pass


class TeacherNotOwnedError(Exception):
    pass


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int) -> None:
        super().__init__(cost)
        self.cost = cost


class LessonOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class NoStudentsError(Exception):
    """Некого учить: нет статистов без школы и учеников этой школы ниже максимума."""


class SchoolBusyError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TeacherView:
    event_id: int
    school: str
    unlocked: bool  # уже в магазине или куплен
    quest: QuestView | None
    ends_in_seconds: int


@dataclass(frozen=True, slots=True)
class ShopTeacher:
    school: str
    owned: bool
    cooldown: int  # до следующего занятия (только у купленных)


@dataclass(frozen=True, slots=True)
class LessonResult:
    school: str
    joined: int
    leveled: int
    price: int


async def _schools(session: AsyncSession, user_id: int) -> dict[str, bool]:
    rows = await session.execute(select(UserSchool.school, UserSchool.owned).where(UserSchool.user_id == user_id))
    return {r[0]: r[1] for r in rows.all()}


async def get_teacher(session: AsyncSession, user_id: int, event_id: int) -> TeacherView:
    event = await event_repo.get_active(session, event_id, user_id)
    if event is None or event.kind != EVENT_SCHOOL_TEACHER:
        raise TeacherGoneError
    quests = {q.ref: q for q in await list_active(session, user_id, QUEST_SCHOOL)}
    return TeacherView(
        event_id=event.id,
        school=event.code,
        unlocked=event.code in await _schools(session, user_id),
        quest=quests.get(event.code),
        ends_in_seconds=max(0, int((event.ends_at - datetime.now(timezone.utc)).total_seconds())),
    )


async def meet(session: AsyncSession, user_id: int, event_id: int) -> QuestView:
    """Встреча с учителем на карте — он даёт задание. Коммитит."""
    view = await get_teacher(session, user_id, event_id)
    if view.unlocked:
        raise AlreadyUnlockedError
    if not await start(session, user_id, QUEST_SCHOOL, view.school, SCHOOL_QUESTS[view.school]):
        raise QuestAlreadyActiveError
    await session.commit()
    return {q.ref: q for q in await list_active(session, user_id, QUEST_SCHOOL)}[view.school]


async def claim_quest(session: AsyncSession, user_id: int, school: str) -> None:
    """Выполненное задание → учитель появляется в магазине. Коммитит."""
    if school not in SCHOOLS:
        raise UnknownSchoolError(school)
    if await claim(session, user_id, QUEST_SCHOOL, school) is None:
        raise QuestNotCompleteError
    await session.execute(pg_insert(UserSchool).values(user_id=user_id, school=school).on_conflict_do_nothing())
    await session.commit()


async def quests(session: AsyncSession, user_id: int) -> list[QuestView]:
    return await list_active(session, user_id, QUEST_SCHOOL)


async def shop_teachers(session: AsyncSession, redis: Redis, user_id: int) -> list[ShopTeacher]:
    result = []
    for school, owned in (await _schools(session, user_id)).items():
        cooldown = max(0, await redis.ttl(school_lesson_cooldown(user_id, school))) if owned else 0
        result.append(ShopTeacher(school, owned, cooldown))
    return sorted(result, key=lambda t: SCHOOLS.index(t.school))


async def buy_teacher(session: AsyncSession, redis: Redis, user_id: int, school: str) -> None:
    """Купить учителя (он должен быть в магазине). Лок на клик + атомарное списание. Коммитит."""
    schools = await _schools(session, user_id)
    if school not in schools:
        raise TeacherNotUnlockedError
    if schools[school]:
        raise TeacherAlreadyOwnedError
    key = action_lock(user_id, LOCK_ACTION_SCHOOL)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise SchoolBusyError
    try:
        result = await session.execute(
            update(UserSchool)
            .where(UserSchool.user_id == user_id, UserSchool.school == school, UserSchool.owned.is_(False))
            .values(owned=True)
        )
        if not result.rowcount:
            raise TeacherAlreadyOwnedError
        if not await business_repo.spend_coins(session, user_id, SCHOOL_TEACHER_PRICE):
            await session.rollback()
            raise NotEnoughCoinsError(SCHOOL_TEACHER_PRICE)
        await session.commit()
    finally:
        await redis.delete(key)


async def lesson(session: AsyncSession, redis: Redis, user_id: int, school: str, rng: random.Random | None = None) -> LessonResult:
    """Занятие у купленного учителя. Порядок: учитель куплен → есть кого учить (иначе КД и
    деньги не тратятся) → КД (`SET NX EX`, он же защита от двойного клика) → списание →
    перевод статистов в школу и рост её уровня → один commit; сбой — КД снимается."""
    rng = rng or random.Random()
    if (await _schools(session, user_id)).get(school) is not True:
        raise TeacherNotOwnedError
    stacks = await list_stacks(session, user_id, for_update=True)
    students = [
        s for s in stacks
        if s.school == SCHOOL_NONE or (s.school == school and s.school_level < SCHOOL_MAX_LEVEL)
    ]
    if not students:
        raise NoStudentsError
    profile = await get_combat_profile(session, user_id)
    key = school_lesson_cooldown(user_id, school)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(SCHOOL_LESSON_COOLDOWN_SECONDS, profile.eco.extras_training_cooldown)):
        raise LessonOnCooldownError(max(0, await redis.ttl(key)))
    try:
        if not await business_repo.spend_coins(session, user_id, SCHOOL_LESSON_PRICE):
            raise NotEnoughCoinsError(SCHOOL_LESSON_PRICE)
        bonus = (await gym_training_bonus_percent(session, user_id) + profile.eco.extras_training) / 100
        join_p = min(1.0, SCHOOL_JOIN_PERCENT / 100 + bonus)
        up_p = min(1.0, SCHOOL_LEVEL_UP_PERCENT / 100 + bonus)
        joined = leveled = 0
        for s in students:
            covered = rng.binomialvariate(s.quantity, SCHOOL_COVERAGE_PERCENT / 100)
            if not covered:
                continue
            fresh = s.school == SCHOOL_NONE
            moved = rng.binomialvariate(covered, join_p if fresh else up_p)
            # Путь тренировок: не прошедшие пробуют ещё раз.
            if profile.eco.extras_extra_roll and covered > moved:
                moved += rng.binomialvariate(covered - moved, (join_p if fresh else up_p) * min(1.0, profile.eco.extras_extra_roll))
            if not moved:
                continue
            base = {"user_id": user_id, "camp": s.camp, "rank": s.rank, "stars": s.stars, "training_level": s.training_level}
            await add_to_stack(session, **base, quantity=-moved, school=s.school, school_level=s.school_level)
            await add_to_stack(session, **base, quantity=moved, school=school, school_level=1 if fresh else s.school_level + 1)
            if fresh:
                joined += moved
            else:
                leveled += moved
        await emit(session, user_id, TASK_SCHOOL_LESSON)
        await bump_training_reps(session, user_id)
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return LessonResult(school=school, joined=joined, leveled=leveled, price=SCHOOL_LESSON_PRICE)
