"""Лиги: счёт, запуск с переносом территорий и ежедневное повышение (пользователь 2026-11-09).

У каждой лиги своя копия карты: страны `RU`, `RU1` ... `RU4`. Всё, что считается по стране (императоры, налоги,
войны, захват страны), работает внутри своей копии без изменений. Запуск переносит территорию вместе с владельцем,
дальше при повышении она теряется: районы уходят ботам, здания сгорают, трон пропадает, игрок заново выбирает страну
в новой лиге. Вниз лига не падает."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import league_sweep_flag
from bot.config.league import LEAGUE_SWEEP_HOUR_UTC, league_for_score, next_league
from bot.constant.admin.world import CHALLENGE_CANCELLED, RESOLUTION_ADMIN, WAR_CANCELLED
from bot.constant.district import CHALLENGE_PENDING
from bot.constant.empire import WAR_PENDING
from bot.constant.phase import PHASE_GANG
from bot.db.models.user import User
from bot.db.repositories import league as repo
from bot.db.repositories import travel as travel_repo
from bot.services.business import accrue_many
from bot.utils.log_context import reset_source, set_source

_PARAMS = {"cancelled": CHALLENGE_CANCELLED, "admin": RESOLUTION_ADMIN, "pending": CHALLENGE_PENDING, "war_cancelled": WAR_CANCELLED, "war_pending": WAR_PENDING}


class AlreadyLaunchedError(Exception):
    pass


class MapsNotSeededError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class LeagueStatus:
    league: int
    score: int
    next_name: str | None
    next_score: int | None


async def status(session: AsyncSession, user_id: int) -> LeagueStatus:
    row = (await session.execute(text("SELECT league, league_score FROM users WHERE id = :u"), {"u": user_id})).one()
    following = next_league(row[0])
    return LeagueStatus(row[0], row[1], following[0].name if following else None, following[1] if following else None)


async def launch(session_factory: async_sessionmaker[AsyncSession]) -> dict[int, int]:
    """Разовый запуск: распределить всех и перенести их территорию. Одна транзакция. → {лига: игроков}."""
    from bot.services.top import refresh_powers

    async with session_factory() as session:
        if await session.scalar(text("SELECT 1 FROM users WHERE league > 0 LIMIT 1")):
            raise AlreadyLaunchedError
        if not await session.scalar(text("SELECT 1 FROM cities WHERE length(country_code) = 3 LIMIT 1")):
            raise MapsNotSeededError
    await refresh_powers(session_factory, everyone=True)
    token = set_source("league:launch")
    try:
        async with session_factory() as session:
            scores = await repo.all_scores(session)
            await repo.set_scores(session, [(u, s) for u, _, s in scores])
            await repo.set_leagues(session, [(u, league_for_score(s)) for u, _, s in scores if league_for_score(s) > 0])
            await repo.move_to_league_maps(session, _PARAMS)
            await session.commit()
    finally:
        reset_source(token)
    counts: dict[int, int] = {}
    for _, _, s in scores:
        counts[league_for_score(s)] = counts.get(league_for_score(s), 0) + 1
    return counts


async def promote(session: AsyncSession, user_id: int, league: int) -> None:
    """Перевести в лигу: территория и бизнес теряются, страну игрок выбирает заново. Коммитит."""
    user = await travel_repo.lock_user(session, user_id)
    if user is None:
        return
    if user.city_id is not None:
        await accrue_many(session, [user_id])
        await travel_repo.cancel_challenges(session, user_id)
        await travel_repo.abandon_all(session, user_id)
        await repo.strip_territory(session, user_id, {**_PARAMS, "uid": user_id})
    await session.execute(
        update(User).where(User.id == user_id).values(league=league, phase=PHASE_GANG, country_code=None, city_id=None)
    )
    await session.commit()


async def daily_sweep(session_factory: async_sessionmaker[AsyncSession]) -> list[tuple[int, int]]:
    """Пересчитать счёт всем и повысить заслуживших (только вверх). → [(игрок, новая лига)]."""
    from bot.services.top import refresh_powers

    # До разового запуска все ещё в первой лиге: иначе проход поднял бы всех сразу и снял им территорию.
    async with session_factory() as session:
        if not await session.scalar(text("SELECT 1 FROM users WHERE league > 0 LIMIT 1")):
            return []
    await refresh_powers(session_factory, everyone=True)
    async with session_factory() as session:
        scores = await repo.all_scores(session)
        await repo.set_scores(session, [(u, s) for u, _, s in scores])
        await session.commit()
    promoted = []
    token = set_source("league:promotion")
    try:
        for user_id, current, score in scores:
            target = league_for_score(score)
            if target > current:
                async with session_factory() as session:
                    await promote(session, user_id, target)
                promoted.append((user_id, target))
    finally:
        reset_source(token)
    return promoted


async def sweep_due(redis: Redis) -> bool:
    """Пора ли ежедневный пересчёт: один раз в сутки, после `LEAGUE_SWEEP_HOUR_UTC`."""
    now = datetime.now(timezone.utc)
    if now.hour < LEAGUE_SWEEP_HOUR_UTC:
        return False
    return bool(await redis.set(league_sweep_flag(now.date().isoformat()), "1", nx=True, ex=2 * 24 * 3600))
