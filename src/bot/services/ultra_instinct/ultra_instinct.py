"""Ультра инстинкт — автоматика родословной Ямадзаки (сервис).

Пользователь 2026-10-02: Ультра инстинкт — способность родословной Ямадзаки, «позволяет
автоматизировать большинство задач: вербовку, тикеты (крутку уников), тренировки — три
постулата делаются автоматически». Открывается уровнями родословной (`config/bloodline`):
вербовка → тренировки (личная и статистов) → крутка тикетов.

Фоновый проход (`main.py: _ultra_instinct_loop`) раз в `ULTRA_INSTINCT_TICK_SECONDS` берёт
игроков с этой родословной и выполняет за них то же, что сделали бы кнопки, — теми же
сервисами, с теми же КД и атомарностью (действие на КД просто пропускается). Каждое
действие — своя транзакция: сбой одного не мешает остальным.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.constant.bloodline import BLOODLINE_YAMAZAKI
from bot.db.models.gang import Gang
from bot.db.models.user import User
from bot.services.build import get_build

log = logging.getLogger(__name__)

ULTRA_INSTINCT_TICK_SECONDS = 60
ULTRA_INSTINCT_BATCH = 500
# Крутить за проход не больше N тикетов на игрока — автоматика не должна за один проход
# съесть весь запас купленных тикетов, если их сотни.
ULTRA_INSTINCT_ROLLS_PER_TICK = 3


@dataclass
class AutomationReport:
    recruited: int = 0
    trained: int = 0
    extras_trained: int = 0
    rolled: int = 0
    errors: list[str] = field(default_factory=list)


async def _candidates(session: AsyncSession) -> list[tuple[int, str]]:
    rows = await session.execute(
        select(User.id, User.phase)
        .join(Gang, Gang.user_id == User.id)
        .where(User.bloodline == BLOODLINE_YAMAZAKI, User.bloodline_level >= 2, User.city_id.is_not(None))
        .limit(ULTRA_INSTINCT_BATCH)
    )
    return [(r[0], r[1]) for r in rows.all()]


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

    for user_id, phase in candidates:
        async with session_factory() as session:
            eco = (await get_build(session, user_id)).eco
        if eco.auto_recruit:
            await attempt("recruited", lambda s: recruit_extra(s, redis, user_id, phase), (RecruitOnCooldownError,))
        if eco.auto_train:
            await attempt("trained", lambda s: train_personal(s, redis, user_id), (TrainingOnCooldownError,))
            await attempt("extras_trained", lambda s: train_extras(s, redis, user_id, phase), (TrainingOnCooldownError,))
        if eco.auto_roll:
            for _ in range(ULTRA_INSTINCT_ROLLS_PER_TICK):
                if not await attempt("rolled", lambda s: roll(s, redis, user_id), (NoTicketsError, RollBusyError)):
                    break  # тикеты кончились — дальше не крутим
    return report
