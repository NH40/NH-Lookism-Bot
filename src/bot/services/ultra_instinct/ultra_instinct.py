"""Ультра инстинкт — автоматика родословной Ямадзаки (сервис).

Пользователь 2026-10-02: Ультра инстинкт — способность родословной Ямадзаки, «позволяет
автоматизировать большинство задач». 2026-11-04: покрывает вербовку, личную тренировку, тренировку
статистов, занятия у учителей и крутку тикетов; на последнем уровне родословной — автобой с выбранными
боссами; игрок может включать и выключать каждый пункт.

Фоновый проход (`main.py: _ultra_instinct_loop`) раз в `ULTRA_INSTINCT_TICK_SECONDS` берёт
игроков с этой родословной и выполняет за них то же, что сделали бы кнопки, — теми же
сервисами, с теми же КД и атомарностью (действие на КД просто пропускается). Каждое
действие — своя транзакция: сбой одного не мешает остальным.

**Автобой с боссом может стоить много армии** (пользователь: «игрок может так терять очень много
статистов»). Поэтому перед каждым автобоем считается прогноз тем же движком боя: бой идёт, только если
шанс победы не ниже `ULTRA_BOSS_MIN_WIN_RATE` и ожидаемые потери не выше потолка, который игрок задал сам.
По умолчанию боссы не выбраны, то есть автобой выключен.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.constant.bloodline import BLOODLINE_YAMAZAKI
from bot.constant.event import BOSSES as BOSS_CODES, EVENT_BOSS
from bot.constant.extra import CAMP_ATTACK
from bot.constant.ultra_instinct import (
    ACTION_EXTRAS,
    ACTION_RECRUIT,
    ACTION_ROLL,
    ACTION_SCHOOL,
    ACTION_TRAIN,
    ACTIONS,
    KEY_BOSSES,
    KEY_MAX_LOSS,
    KEY_OFF,
)
from bot.db.models.gang import Gang
from bot.db.models.user import User
from bot.services.build import get_build

log = logging.getLogger(__name__)

ULTRA_INSTINCT_TICK_SECONDS = 60
ULTRA_INSTINCT_BATCH = 500
# Крутить за проход не больше N тикетов на игрока — автоматика не должна за один проход
# съесть весь запас купленных тикетов, если их сотни.
ULTRA_INSTINCT_ROLLS_PER_TICK = 3
# Автобой с боссом: прогноз должен обещать победу, потери — ниже потолка игрока.
ULTRA_BOSS_MIN_WIN_RATE = 0.75
ULTRA_BOSS_FORECAST_LEVEL = 2  # 16 симуляций: честная оценка без лишней нагрузки на проход
ULTRA_LOSS_OPTIONS: tuple[int, ...] = (10, 25, 50, 75)
ULTRA_LOSS_DEFAULT = 25


class UltraUnavailableError(Exception):
    """У игрока нет этой способности."""


class MaxLossError(Exception):
    pass


@dataclass
class AutomationReport:
    recruited: int = 0
    trained: int = 0
    extras_trained: int = 0
    lessons: int = 0
    rolled: int = 0
    bosses: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class UltraView:
    available: dict[str, bool]  # какие действия открыты уровнем родословной
    enabled: dict[str, bool]  # какие включены
    boss_available: bool
    bosses: tuple[str, ...]  # выбранные боссы
    max_loss: int


def _available(eco) -> dict[str, bool]:
    return {
        ACTION_RECRUIT: eco.auto_recruit,
        ACTION_TRAIN: eco.auto_train,
        ACTION_EXTRAS: eco.auto_train,
        ACTION_SCHOOL: eco.auto_school,
        ACTION_ROLL: eco.auto_roll,
    }


def _enabled(settings: dict, action: str) -> bool:
    return action not in (settings or {}).get(KEY_OFF, ())


async def get_view(session: AsyncSession, user_id: int) -> UltraView:
    eco = (await get_build(session, user_id)).eco
    available = _available(eco)
    if not any(available.values()):
        raise UltraUnavailableError
    settings = await session.scalar(select(User.ultra_settings).where(User.id == user_id)) or {}
    return UltraView(
        available=available,
        enabled={a: _enabled(settings, a) for a in ACTIONS},
        boss_available=eco.auto_boss,
        bosses=tuple(c for c in settings.get(KEY_BOSSES, ()) if c in BOSS_CODES),
        max_loss=int(settings.get(KEY_MAX_LOSS, ULTRA_LOSS_DEFAULT)),
    )


async def _locked_settings(session: AsyncSession, user_id: int) -> dict:
    return dict(await session.scalar(select(User.ultra_settings).where(User.id == user_id).with_for_update()) or {})


async def _save(session: AsyncSession, user_id: int, settings: dict) -> None:
    await session.execute(update(User).where(User.id == user_id).values(ultra_settings=settings))
    await session.commit()


async def toggle_action(session: AsyncSession, user_id: int, action: str) -> bool:
    """Включить/выключить одно действие. Коммитит. → включено ли теперь."""
    if action not in ACTIONS or not _available((await get_build(session, user_id)).eco).get(action):
        raise UltraUnavailableError
    settings = await _locked_settings(session, user_id)
    off = set(settings.get(KEY_OFF, ()))
    enabled = action in off
    (off.discard if enabled else off.add)(action)
    settings[KEY_OFF] = sorted(off)
    await _save(session, user_id, settings)
    return enabled


async def toggle_boss(session: AsyncSession, user_id: int, code: str) -> bool:
    """Добавить/убрать босса из автобоя. Коммитит. → выбран ли теперь."""
    if code not in BOSS_CODES or not (await get_build(session, user_id)).eco.auto_boss:
        raise UltraUnavailableError
    settings = await _locked_settings(session, user_id)
    bosses = set(settings.get(KEY_BOSSES, ()))
    selected = code not in bosses
    (bosses.add if selected else bosses.discard)(code)
    settings[KEY_BOSSES] = sorted(bosses)
    await _save(session, user_id, settings)
    return selected


async def set_max_loss(session: AsyncSession, user_id: int, percent: int) -> None:
    """Потолок ожидаемых потерь автобоя. Коммитит."""
    if percent not in ULTRA_LOSS_OPTIONS:
        raise MaxLossError
    if not (await get_build(session, user_id)).eco.auto_boss:
        raise UltraUnavailableError
    settings = await _locked_settings(session, user_id)
    settings[KEY_MAX_LOSS] = percent
    await _save(session, user_id, settings)


async def _candidates(session: AsyncSession) -> list[tuple[int, str, dict]]:
    rows = await session.execute(
        select(User.id, User.phase, User.ultra_settings)
        .join(Gang, Gang.user_id == User.id)
        .where(
            or_(
                (User.bloodline == BLOODLINE_YAMAZAKI) & (User.bloodline_level >= 2),
                (User.bloodline2 == BLOODLINE_YAMAZAKI) & (User.bloodline2_level >= 2) & User.second_body.is_(True),
            ),
            User.city_id.is_not(None),
        )
        .limit(ULTRA_INSTINCT_BATCH)
    )
    return [(r[0], r[1], r[2] or {}) for r in rows.all()]


async def _safe_boss_fights(session_factory, redis: Redis, user_id: int, settings: dict, attempt) -> None:
    """Автобой с выбранными боссами на карте, если прогноз обещает победу и потери ниже потолка."""
    from bot.db.repositories import event as event_repo
    from bot.db.repositories.user import get_by_id
    from bot.services.characteristic import get_combat_profile
    from bot.services.district.army import load_camp
    from bot.services.district.boss import (
        BossAlreadyDefeatedError,
        EventGoneError,
        boss_army,
        boss_chances,
        fight_boss,
    )
    from bot.services.district.district import BattleOnCooldownError, NoAttackersError
    from bot.services.country import BattlesClosedError
    from bot.services.foresight.foresight import _simulate

    chosen = set(settings.get(KEY_BOSSES, ()))
    if not chosen:
        return
    max_loss = int(settings.get(KEY_MAX_LOSS, ULTRA_LOSS_DEFAULT)) / 100
    async with session_factory() as session:
        user = await get_by_id(session, user_id)
        targets = [
            (e.id, e.code) for e, won, _ in await event_repo.list_active(session, user_id)
            if e.kind == EVENT_BOSS and e.code in chosen and not won
        ]
        if user is None or not targets:
            return
        stacks = await load_camp(session, user_id, CAMP_ATTACK, for_update=False)
        if not stacks:
            return
        profile = await get_combat_profile(session, user_id)
    for event_id, code in targets:
        boss, _ = boss_army(code, stacks, user.phase)
        forecast = _simulate(stacks, profile.chances(), boss, boss_chances(code), ULTRA_BOSS_FORECAST_LEVEL)
        if forecast.win_rate < ULTRA_BOSS_MIN_WIN_RATE or forecast.loss_share > max_loss:
            continue
        fought = await attempt(
            "bosses", lambda s, ev=event_id: _fight(s, redis, user_id, ev, fight_boss, get_by_id),
            (BossAlreadyDefeatedError, EventGoneError, BattleOnCooldownError, NoAttackersError, BattlesClosedError),
        )
        if fought:
            return  # один бой за проход: дальше общий КД боссов


async def _fight(session: AsyncSession, redis: Redis, user_id: int, event_id: int, fight_boss, get_by_id) -> None:
    user = await get_by_id(session, user_id)
    await fight_boss(session, redis, user, event_id)


async def _school_lessons(session_factory, redis: Redis, user_id: int, attempt) -> None:
    """Занятия у всех купленных учителей школ: у каждого свой КД."""
    from bot.services.school import shop_teachers
    from bot.services.school.school import LessonOnCooldownError, NoStudentsError, NotEnoughCoinsError, lesson

    async with session_factory() as session:
        teachers = await shop_teachers(session, redis, user_id)
    for teacher in teachers:
        if teacher.owned and not teacher.cooldown:
            await attempt(
                "lessons", lambda s, code=teacher.school: lesson(s, redis, user_id, code),
                (LessonOnCooldownError, NoStudentsError, NotEnoughCoinsError),
            )


async def run_once(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> AutomationReport:
    # Отложенные импорты: сервисы действий сами тянут много доменов.
    from bot.services.gacha import NoTicketsError, RollBusyError, roll
    from bot.services.recruit import RecruitOnCooldownError, recruit_extra
    from bot.services.training import TrainingOnCooldownError, train_extras
    from bot.services.training.personal import train_personal

    report = AutomationReport()
    async with session_factory() as session:
        candidates = await _candidates(session)

    async def attempt(name: str, action, expected: tuple) -> bool:
        """Одно действие своей транзакцией. → False — ожидаемый отказ (КД, нет тикетов)."""
        async with session_factory() as session:
            try:
                await action(session)
            except expected:
                await session.rollback()
                return False
            except Exception as exc:  # одно действие не валит проход
                await session.rollback()
                report.errors.append(f"{name}:{exc!r}")
                log.exception("Ultra instinct action failed")
                return False
        setattr(report, name, getattr(report, name) + 1)
        return True

    for user_id, phase, settings in candidates:
        async with session_factory() as session:
            eco = (await get_build(session, user_id)).eco
        if eco.auto_recruit and _enabled(settings, ACTION_RECRUIT):
            await attempt("recruited", lambda s: recruit_extra(s, redis, user_id, phase), (RecruitOnCooldownError,))
        if eco.auto_train and _enabled(settings, ACTION_TRAIN):
            await attempt("trained", lambda s: train_personal(s, redis, user_id), (TrainingOnCooldownError,))
        if eco.auto_train and _enabled(settings, ACTION_EXTRAS):
            await attempt("extras_trained", lambda s: train_extras(s, redis, user_id, phase), (TrainingOnCooldownError,))
        if eco.auto_school and _enabled(settings, ACTION_SCHOOL):
            await _school_lessons(session_factory, redis, user_id, attempt)
        if eco.auto_roll and _enabled(settings, ACTION_ROLL):
            for _ in range(ULTRA_INSTINCT_ROLLS_PER_TICK):
                if not await attempt("rolled", lambda s: roll(s, redis, user_id), (NoTicketsError, RollBusyError)):
                    break  # тикеты кончились — дальше не крутим
        if eco.auto_boss:
            await _safe_boss_fights(session_factory, redis, user_id, settings, attempt)
    return report
