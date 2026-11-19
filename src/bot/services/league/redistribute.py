"""Новый счёт лиги и перераспределение из админки (пользователь 2026-11-19).

Счёт = прежняя формула в SQL (`repo.all_scores`) + доход в час (логарифмом) + прибавка за место клана в топе.

Перераспределение — разово и в обе стороны: каждому лига по счёту и текущим порогам (их меняют в админке).
Территория переезжает с игроком на карту новой лиги (копия той же страны, тот же город):
- район — с тем же номером, если он там свободен, иначе любой свободный в том же городе; свободных нет —
  район уходит, а здания на нём возвращаются NHCoin по базовой цене постройки;
- трон — если в новой лиге у города нет императора; занят — город теряется, его владения сгорают.
  Остался император без единого города — становится кругом (воевать за город снова может только круг).
Вызовы на районы и войны императоров между разными лигами отменяются. Всё — одной транзакцией.
"""
from __future__ import annotations

import logging
import math
import random
from collections import Counter
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import league as league_cfg
from bot.config.game import BUSINESS_BUILD_COST
from bot.constant.admin.world import CHALLENGE_CANCELLED, RESOLUTION_ADMIN, WAR_CANCELLED
from bot.constant.district import CHALLENGE_PENDING
from bot.constant.empire import WAR_PENDING
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST
from bot.db.repositories import league as repo
from bot.utils.log_context import reset_source, set_source

log = logging.getLogger(__name__)

_LOCK_KEY = "league:redistribute"
_LOCK_SECONDS = 1800


class RedistributeBusyError(Exception):
    """Перераспределение уже идёт."""


@dataclass(frozen=True, slots=True)
class Plan:
    counts: dict[int, int]  # лига → игроков после
    moves: dict[tuple[int, int], int]  # (было, станет) → игроков
    up: int
    down: int


@dataclass(frozen=True, slots=True)
class Result:
    plan: Plan
    districts_moved: int
    districts_lost: int
    refunded: int
    thrones_moved: int
    thrones_lost: int
    moved: list[tuple[int, int, int]]  # (игрок, было, стало)


def _clan_bonus(rank: int | None) -> int:
    if rank is None:
        return 0
    if rank < 3:
        return league_cfg.league.SCORE_CLAN_TOP3
    if rank < 10:
        return league_cfg.league.SCORE_CLAN_TOP10
    return league_cfg.league.SCORE_CLAN_TOP25


async def compute_scores(session: AsyncSession) -> list[tuple[int, int, int]]:
    """(игрок, текущая лига, новый счёт) всех игроков."""
    from bot.db.repositories.clan.clan import top_page
    from bot.services.business.business import income_for

    base = await repo.all_scores(session)
    counts, levels = await repo.income_counts(session)
    top = {c.id: i for i, (c, _) in enumerate(await top_page(session, 25, 0))}
    clan_of = await repo.clan_of_all(session)
    weight = league_cfg.league.SCORE_INCOME_LOG
    result = []
    for uid, current, score in base:
        rate = income_for(counts[uid], levels.get(uid, 0), 60, random.Random(0)) if uid in counts else 0
        extra = weight * math.log10(max(rate, 0) + 1) + _clan_bonus(top.get(clan_of.get(uid)))
        result.append((uid, current, int(round(score + extra))))
    return result


def _plan(scores: list[tuple[int, int, int]]) -> Plan:
    targets = [(cur, league_cfg.league_for_score(s)) for _, cur, s in scores]
    moves = Counter((a, b) for a, b in targets if a != b)
    return Plan(
        counts=dict(sorted(Counter(b for _, b in targets).items())), moves=dict(sorted(moves.items())),
        up=sum(n for (a, b), n in moves.items() if b > a), down=sum(n for (a, b), n in moves.items() if b < a),
    )


async def preview(session: AsyncSession) -> Plan:
    """Что будет, если раскидать сейчас (мощь — из последнего снимка, без пересчёта)."""
    return _plan(await compute_scores(session))


def _league_of_code(code: str) -> int:
    return 0 if len(code) == 2 else int(code[-1])


async def _move_territory(session: AsyncSession, moves: dict[int, int]) -> tuple[int, int, int, int, int]:
    """Перенести территорию переехавших на карту новой лиги. НЕ коммитит. → (районов, потеряно, возврат, тронов, потеряно)."""
    cities = (await session.execute(text("SELECT id, country_code, name, emperor_id FROM cities"))).all()
    by_key = {(code[:2], name, _league_of_code(code)): (cid, code) for cid, code, name, _ in cities}
    info = {cid: (code, name) for cid, code, name, _ in cities}
    emperor = {cid: emp for cid, _, _, emp in cities}

    def counterpart(city_id: int, league: int) -> tuple[int, str] | None:
        code, name = info[city_id]
        return by_key.get((code[:2], name, league))

    ids = list(moves)
    # --- районы
    owned = (await session.execute(text(
        "SELECT d.id, d.owner_id, d.city_id, d.number, d.captured_at FROM districts d WHERE d.owner_id = ANY(:ids) ORDER BY d.id"
    ), {"ids": ids})).all()
    owned = [r for r in owned if _league_of_code(info[r[2]][0]) != moves[r[1]]]
    target_cities = {cp[0] for r in owned if (cp := counterpart(r[2], moves[r[1]]))}
    free: dict[int, dict[int, int]] = {}  # город → {номер: id свободного района}
    if target_cities:
        for did, cid, num in (await session.execute(text(
            "SELECT id, city_id, number FROM districts WHERE city_id = ANY(:c) AND owner_id IS NULL ORDER BY number"
        ), {"c": list(target_cities)})).all():
            free.setdefault(cid, {})[num] = did
    moved = lost = refunded = 0
    lost_districts: list[int] = []
    # Два прохода: сначала все, кому свободен район с тем же номером, потом остальные — на любые оставшиеся.
    placed: dict[int, int] = {}
    for did, owner, city_id, number, _ in owned:
        cp = counterpart(city_id, moves[owner])
        slots = free.get(cp[0], {}) if cp else {}
        if number in slots:
            placed[did] = slots.pop(number)
    for did, owner, city_id, number, _ in owned:
        if did in placed:
            continue
        cp = counterpart(city_id, moves[owner])
        slots = free.get(cp[0], {}) if cp else {}
        if slots:
            placed[did] = slots.pop(next(iter(slots)))
    for did, owner, city_id, number, captured in owned:
        new_id = placed.get(did)
        if new_id is None:
            lost_districts.append(did)
            continue
        await session.execute(text("DELETE FROM businesses WHERE district_id = :n"), {"n": new_id})  # сироты на ничейном районе
        await session.execute(text("UPDATE businesses SET district_id = :n WHERE district_id = :o"), {"n": new_id, "o": did})
        await session.execute(text("UPDATE districts SET owner_id = :u, captured_at = :t WHERE id = :n"), {"u": owner, "t": captured, "n": new_id})
        await session.execute(text("UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE id = :o"), {"o": did})
        moved += 1
    if lost_districts:
        rows = (await session.execute(text(
            "SELECT d.owner_id, b.type, count(*) FROM businesses b JOIN districts d ON d.id = b.district_id WHERE d.id = ANY(:d) GROUP BY 1, 2"
        ), {"d": lost_districts})).all()
        back: dict[int, int] = {}
        for owner, type_, n in rows:
            back[owner] = back.get(owner, 0) + BUSINESS_BUILD_COST.get(type_, 0) * int(n)
        await session.execute(text("DELETE FROM businesses WHERE district_id = ANY(:d)"), {"d": lost_districts})
        await session.execute(text("UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE id = ANY(:d)"), {"d": lost_districts})
        for owner, coins in back.items():
            await session.execute(text("UPDATE users SET nh_coins = nh_coins + :c WHERE id = :u"), {"c": coins, "u": owner})
            refunded += coins
        lost = len(lost_districts)
    # --- троны и владения
    thrones_moved = thrones_lost = 0
    for cid, emp in list(emperor.items()):
        if emp not in moves or _league_of_code(info[cid][0]) == moves[emp]:
            continue
        cp = counterpart(cid, moves[emp])
        await session.execute(text("UPDATE cities SET emperor_id = NULL WHERE id = :c"), {"c": cid})
        emperor[cid] = None
        if cp and emperor.get(cp[0]) is None:
            await session.execute(text("UPDATE cities SET emperor_id = :u WHERE id = :c"), {"u": emp, "c": cp[0]})
            await session.execute(text("UPDATE businesses SET origin_city_id = :n WHERE holder_id = :u AND origin_city_id = :o"), {"n": cp[0], "u": emp, "o": cid})
            emperor[cp[0]] = emp
            thrones_moved += 1
        else:
            await session.execute(text("DELETE FROM businesses WHERE holder_id = :u AND origin_city_id = :o AND district_id IS NULL"), {"u": emp, "o": cid})
            thrones_lost += 1
    # Император, у которого не осталось городов, — круг; старые владения без города ему больше не платят.
    lost_all = [u for u in ids if u not in set(emperor.values())]
    if lost_all:
        await session.execute(text(
            "DELETE FROM businesses WHERE holder_id = ANY(:u) AND district_id IS NULL AND EXISTS (SELECT 1 FROM users x WHERE x.id = holder_id AND x.phase = :fist)"
        ), {"u": lost_all, "fist": PHASE_FIST})
        await session.execute(text("UPDATE users SET phase = :circle WHERE id = ANY(:u) AND phase = :fist"), {"u": lost_all, "circle": PHASE_CIRCLE, "fist": PHASE_FIST})
    # --- место жительства
    for uid, city_id in (await session.execute(text("SELECT id, city_id FROM users WHERE id = ANY(:ids) AND city_id IS NOT NULL"), {"ids": ids})).all():
        if _league_of_code(info[city_id][0]) == moves[uid]:
            continue
        cp = counterpart(city_id, moves[uid])
        if cp:
            await session.execute(text("UPDATE users SET city_id = :c, country_code = :k WHERE id = :u"), {"c": cp[0], "k": cp[1], "u": uid})
        else:
            await session.execute(text("UPDATE users SET city_id = NULL, country_code = NULL WHERE id = :u"), {"u": uid})
    return moved, lost, refunded, thrones_moved, thrones_lost


async def redistribute(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> Result:
    """Пересчитать счёт всем (со свежей мощью) и раскидать по лигам в обе стороны."""
    from bot.services.business import accrue_many
    from bot.services.top import refresh_powers

    if not await redis.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_SECONDS):
        raise RedistributeBusyError
    token = set_source("league:redistribute")
    try:
        await refresh_powers(session_factory, everyone=True)
        async with session_factory() as session:
            scores = await compute_scores(session)
            plan = _plan(scores)
            moves = {u: league_cfg.league_for_score(s) for u, cur, s in scores if league_cfg.league_for_score(s) != cur}
            await repo.set_scores(session, [(u, s) for u, _, s in scores])
            if moves:
                await accrue_many(session, sorted(moves))  # доход по старому месту — до переезда
                params = {"cancelled": CHALLENGE_CANCELLED, "admin": RESOLUTION_ADMIN, "pending": CHALLENGE_PENDING, "ids": list(moves)}
                await session.execute(text(
                    """UPDATE district_challenges c SET status = :cancelled, resolution = :admin, resolved_at = now()
                       WHERE c.status = :pending AND (c.attacker_id = ANY(:ids) OR c.defender_id = ANY(:ids)
                         OR c.district_id IN (SELECT id FROM districts WHERE owner_id = ANY(:ids)))"""
                ), params)
                await repo.set_leagues(session, sorted(moves.items()))
                await session.execute(text(
                    """UPDATE emperor_wars w SET status = :war_cancelled, resolution = :admin, resolved_at = now()
                       FROM users a, users d WHERE w.status = :war_pending AND a.id = w.attacker_id AND d.id = w.defender_id AND a.league <> d.league"""
                ), {"war_cancelled": WAR_CANCELLED, "admin": RESOLUTION_ADMIN, "war_pending": WAR_PENDING})
                stats = await _move_territory(session, moves)
                await session.execute(text(
                    "DELETE FROM emperor_tax_overrides t USING users e, users p WHERE e.id = t.emperor_id AND p.id = t.user_id AND e.league <> p.league"
                ))
            else:
                stats = (0, 0, 0, 0, 0)
            await session.commit()
        moved = sorted((u, cur, moves[u]) for u, cur, _ in scores if u in moves)
        log.info("League redistribute: %s moved, stats %s", len(moved), stats)
        return Result(plan, *stats, moved=moved)
    finally:
        reset_source(token)
        await redis.delete(_LOCK_KEY)
