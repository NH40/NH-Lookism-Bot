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
from bot.config.league import LEAGUE_SWEEP_HOUR_UTC, next_league
from bot.constant.admin.world import CHALLENGE_CANCELLED, RESOLUTION_ADMIN, WAR_CANCELLED
from bot.constant.district import CHALLENGE_PENDING
from bot.constant.empire import WAR_PENDING
from bot.constant.phase import PHASE_GANG
from bot.db.models.user import User
from bot.db.repositories import league as repo
from bot.db.repositories import travel as travel_repo
from bot.services.business import accrue_many
from bot.utils.log_context import reset_source, set_source
from bot.services.league.redistribute import compute_scores

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
            scores = await compute_scores(session)
            await repo.set_scores(session, [(u, s) for u, _, s, _ in scores])
            await repo.set_leagues(session, [(u, t) for u, _, _, t in scores if t > 0])
            await repo.move_to_league_maps(session, _PARAMS)
            await session.commit()
    finally:
        reset_source(token)
    counts: dict[int, int] = {}
    for _, _, _, t in scores:
        counts[t] = counts.get(t, 0) + 1
    return counts


async def promote(session: AsyncSession, user_id: int, league: int, *, keep_territory: bool = False):
    """Перевести в лигу. Коммитит.
    `keep_territory` (ежедневное повышение, 2026-11-23) — территория переезжает: свободные районы со зданиями, на
    занятые — заявки с бесплатным вызовом на 24 часа (`services/league/move`) → `MoveReport`.
    Иначе (неактивный вниз, ручная смена в админке) — всё теряется, страна заново → None."""
    user = await travel_repo.lock_user(session, user_id)
    if user is None:
        return None
    if keep_territory:
        from bot.services.league.move import move_on_promotion

        if user.city_id is not None:
            await accrue_many(session, [user_id])
            await travel_repo.cancel_challenges(session, user_id)
        report = await move_on_promotion(session, user_id, league)
        await session.commit()
        return report
    if user.city_id is not None:
        await accrue_many(session, [user_id])
        await travel_repo.cancel_challenges(session, user_id)
        await travel_repo.abandon_all(session, user_id)
        await repo.strip_territory(session, user_id, {**_PARAMS, "uid": user_id})
    await session.execute(
        update(User).where(User.id == user_id).values(league=league, phase=PHASE_GANG, country_code=None, city_id=None)
    )
    await session.commit()
    return None


async def daily_sweep(session_factory: async_sessionmaker[AsyncSession]) -> tuple[list[tuple], list[tuple[int, int]]]:
    """Пересчитать счёт всем, повысить заслуживших и (лиги по силе) опустить неактивных на одну лигу.
    → ([(игрок, новая лига, отчёт переезда) повышенные], [(игрок, новая лига) опущенные])."""
    from bot.config import league as cfg
    from bot.services.top import refresh_powers

    # До разового запуска все ещё в первой лиге: иначе проход поднял бы всех сразу и снял им территорию.
    async with session_factory() as session:
        if not await session.scalar(text("SELECT 1 FROM users WHERE league > 0 LIMIT 1")):
            return [], []
    await refresh_powers(session_factory, everyone=True)
    async with session_factory() as session:
        scores = await compute_scores(session)
        await repo.set_scores(session, [(u, s) for u, _, s, _ in scores])
        inactive: set[int] = set()
        if cfg.league.LEAGUE_STATIC_AXES:
            inactive = {int(u) for (u,) in (await session.execute(text(
                "SELECT id FROM users WHERE league > 0 AND last_active_at < now() - make_interval(days => :d)"
            ), {"d": int(cfg.league.LEAGUE_INACTIVE_DAYS)})).all()}
        await session.commit()
    promoted, demoted = [], []
    token = set_source("league:promotion")
    try:
        for user_id, current, _score, target in scores:
            if target > current:
                async with session_factory() as session:
                    report = await promote(session, user_id, target, keep_territory=True)
                promoted.append((user_id, target, report))
            elif target < current and user_id in inactive:  # неактивный и уже слабее своей лиги — на одну вниз
                async with session_factory() as session:
                    await promote(session, user_id, current - 1)
                demoted.append((user_id, current - 1))
    finally:
        reset_source(token)
    return promoted, demoted


async def sweep_due(redis: Redis) -> bool:
    """Пора ли ежедневный пересчёт: один раз в сутки, после `LEAGUE_SWEEP_HOUR_UTC`."""
    now = datetime.now(timezone.utc)
    if now.hour < LEAGUE_SWEEP_HOUR_UTC:
        return False
    return bool(await redis.set(league_sweep_flag(now.date().isoformat()), "1", nx=True, ex=2 * 24 * 3600))
