"""Ивенты императора для подданных (пользователь 2026-11-10: «чтобы император не только забирал
налог, но и мог запускать ивенты, давать бонусы и бафы»; виды выбраны пользователем).

Подданные — игроки в городах императора на момент действия (налог ему платят они же). Всё
оплачено заранее из NHCoin императора, новых денег в игре не появляется:

- раздача NHCoin / статистов — фонд на N мест, каждый подданный забирает один раз за 24 ч;
- ежедневный подарок — фонд на N дней, подданный забирает раз в сутки (UTC);
- праздник — подданные получают +X% дохода, бонус платится из фонда, пока он не кончится;
- турнир — фонд делят 3 подданных с наибольшим числом побед в PvP за сутки (50/30/20%);
- военные сборы — −X% КД тренировок, монеты сгорают (цена по числу активных подданных);
- налоговые каникулы — налог 0%, бесплатно (император просто не получает налог).

Остаток фонда по окончании возвращается императору. Один активный ивент каждого вида,
перезарядка вида — от запуска. Строки: сначала игрок, потом ивент, потом император — тот же
порядок, что при сборе дохода (`services/business.accrue`), без взаимоблокировок.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.characteristic import extra_power_for_rank
from bot.config.characteristic.characteristic import RANK_INDEX
from bot.config.empire import (
    EMPIRE_DAILY_GIFT_MAX_DAYS,
    EMPIRE_DRILL_CD_PERCENT,
    EMPIRE_DRILL_PRICE_PER_SUBJECT_HOUR,
    EMPIRE_EVENT_CLAIM_HOURS,
    EMPIRE_EVENT_COOLDOWN_HOURS,
    EMPIRE_EVENT_DURATIONS_HOURS,
    EMPIRE_EVENT_MAX_SLOTS,
    EMPIRE_EVENT_MIN_FUND,
    EMPIRE_FEAST_INCOME_PERCENT,
    EMPIRE_GIFT_COINS_PER_POWER,
    EMPIRE_GIFT_MAX_RANK,
    EMPIRE_TOURNAMENT_HOURS,
    EMPIRE_TOURNAMENT_SHARES,
)
from bot.constant.empire import (
    EVENT_ACTIVE,
    EVENT_COINS,
    EVENT_DAILY,
    EVENT_DONE,
    EVENT_DRILL,
    EVENT_FEAST,
    EVENT_HOLIDAY,
    EVENT_KINDS,
    EVENT_STATISTS,
    EVENT_TOURNAMENT,
)
from bot.constant.extra import CAMP_DEFENSE
from bot.constant.ledger import REASON_EMPIRE_EVENT
from bot.db.models.empire_event import EmpireEvent
from bot.db.repositories import business as business_repo
from bot.utils.log_context import coin_reason

log = logging.getLogger(__name__)


class NotEmperorError(Exception):
    pass


class EventActiveError(Exception):
    """Такой ивент уже идёт."""


class EventCooldownError(Exception):
    def __init__(self, seconds: int) -> None:
        super().__init__(seconds)
        self.seconds = seconds


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int) -> None:
        super().__init__(cost)
        self.cost = cost


class BadParamsError(Exception):
    pass


class NoSubjectsError(Exception):
    pass


class EventGoneError(Exception):
    """Ивент закончился, не твоей империи или не найден."""


class AlreadyClaimedError(Exception):
    pass


class EventEmptyError(Exception):
    """Фонд или места кончились."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- кто чей ---


async def emperor_of(session: AsyncSession, user_id: int) -> int | None:
    """Император города игрока (None — города без императора или он сам себе император)."""
    emperor = await session.scalar(text(
        "SELECT c.emperor_id FROM users u JOIN cities c ON c.id = u.city_id WHERE u.id = :u"
    ), {"u": user_id})
    return emperor if emperor and emperor != user_id else None


async def _is_subject(session: AsyncSession, user_id: int, emperor_id: int) -> bool:
    return await emperor_of(session, user_id) == emperor_id


async def _ensure_emperor(session: AsyncSession, user_id: int) -> None:
    if not await session.scalar(text("SELECT EXISTS(SELECT 1 FROM cities WHERE emperor_id = :u)"), {"u": user_id}):
        raise NotEmperorError


async def subject_counts(session: AsyncSession, emperor_id: int) -> tuple[int, int]:
    """(все подданные, заходившие за сутки)."""
    row = (await session.execute(text(
        "SELECT count(*), count(*) FILTER (WHERE u.last_active_at > now() - interval '24 hours') "
        "FROM users u JOIN cities c ON c.id = u.city_id WHERE c.emperor_id = :e AND u.id <> :e"
    ), {"e": emperor_id})).one()
    return int(row[0]), int(row[1])


async def _league(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(text("SELECT league FROM users WHERE id = :u"), {"u": user_id}) or 0)


# --- экран императора ---


@dataclass(frozen=True, slots=True)
class KindView:
    kind: str
    active: EmpireEvent | None
    cooldown_seconds: int


async def kinds_view(session: AsyncSession, emperor_id: int) -> list[KindView]:
    rows = (await session.execute(
        select(EmpireEvent).where(EmpireEvent.emperor_id == emperor_id).order_by(EmpireEvent.created_at.desc()).limit(50)
    )).scalars().all()
    now = _now()
    out = []
    for kind in EVENT_KINDS:
        mine = [r for r in rows if r.kind == kind]
        active = next((r for r in mine if r.status == EVENT_ACTIVE), None)
        last = mine[0].created_at if mine else None
        ready = last + timedelta(hours=EMPIRE_EVENT_COOLDOWN_HOURS.get(kind, 0)) if last else now
        out.append(KindView(kind, active, max(0, int((ready - now).total_seconds())) if active is None else 0))
    return out


async def drill_price(session: AsyncSession, emperor_id: int, hours: int) -> int:
    _, active = await subject_counts(session, emperor_id)
    table = EMPIRE_DRILL_PRICE_PER_SUBJECT_HOUR
    league = min(max(await _league(session, emperor_id), 0), len(table) - 1)
    return max(1, active) * hours * table[league]


def statist_unit_price(rank: str) -> int:
    return extra_power_for_rank(rank) * EMPIRE_GIFT_COINS_PER_POWER


# --- запуск ---


@dataclass(frozen=True, slots=True)
class Started:
    event_id: int
    kind: str
    emperor_id: int
    cost: int
    params: dict
    ends_at: datetime


async def _start(
    session: AsyncSession, emperor_id: int, kind: str, *, hours: int, cost: int, pool: int = 0, units: int = 0,
    slots: int = 0, params: dict | None = None,
) -> Started:
    """Проверки → списание → строка ивента → commit. Двойной клик — частичный уникальный индекс."""
    await _ensure_emperor(session, emperor_id)
    view = next(v for v in await kinds_view(session, emperor_id) if v.kind == kind)
    if view.active is not None:
        raise EventActiveError
    if view.cooldown_seconds > 0:
        raise EventCooldownError(view.cooldown_seconds)
    if cost > 0:
        with coin_reason(REASON_EMPIRE_EVENT):
            if not await business_repo.spend_coins(session, emperor_id, cost):
                raise NotEnoughCoinsError(cost)
    ends_at = _now() + timedelta(hours=hours)
    row = EmpireEvent(
        emperor_id=emperor_id, kind=kind, status=EVENT_ACTIVE, params=params or {}, pool=pool, units=units,
        slots=slots, ends_at=ends_at,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise EventActiveError from None
    await session.commit()
    return Started(row.id, kind, emperor_id, cost, dict(row.params), ends_at)


def _check_hours(hours: int) -> int:
    if hours not in EMPIRE_EVENT_DURATIONS_HOURS:
        raise BadParamsError
    return hours


async def start_coins(session: AsyncSession, emperor_id: int, per_player: int, slots: int) -> Started:
    if per_player < 1 or not 1 <= slots <= EMPIRE_EVENT_MAX_SLOTS:
        raise BadParamsError
    total = per_player * slots
    return await _start(
        session, emperor_id, EVENT_COINS, hours=EMPIRE_EVENT_CLAIM_HOURS, cost=total, pool=total, slots=slots,
        params={"per": per_player},
    )


async def start_statists(session: AsyncSession, emperor_id: int, rank: str, per_player: int, slots: int) -> Started:
    if (
        rank not in RANK_INDEX or RANK_INDEX[rank] > RANK_INDEX[EMPIRE_GIFT_MAX_RANK]
        or per_player < 1 or not 1 <= slots <= EMPIRE_EVENT_MAX_SLOTS
    ):
        raise BadParamsError
    units = per_player * slots
    return await _start(
        session, emperor_id, EVENT_STATISTS, hours=EMPIRE_EVENT_CLAIM_HOURS, cost=units * statist_unit_price(rank),
        units=units, slots=slots, params={"per": per_player, "rank": rank},
    )


async def start_daily(session: AsyncSession, emperor_id: int, per_day: int, days: int) -> Started:
    """Фонд = на день × дней × все подданные сейчас; остаток вернётся."""
    if per_day < 1 or not 1 <= days <= EMPIRE_DAILY_GIFT_MAX_DAYS:
        raise BadParamsError
    subjects, _ = await subject_counts(session, emperor_id)
    if subjects == 0:
        raise NoSubjectsError
    total = per_day * days * subjects
    return await _start(
        session, emperor_id, EVENT_DAILY, hours=24 * days, cost=total, pool=total, params={"per": per_day, "days": days},
    )


async def start_feast(session: AsyncSession, emperor_id: int, hours: int, fund: int) -> Started:
    if fund < EMPIRE_EVENT_MIN_FUND:
        raise BadParamsError
    return await _start(
        session, emperor_id, EVENT_FEAST, hours=_check_hours(hours), cost=fund, pool=fund,
        params={"percent": EMPIRE_FEAST_INCOME_PERCENT, "hours": hours},
    )


async def start_holiday(session: AsyncSession, emperor_id: int, hours: int) -> Started:
    return await _start(session, emperor_id, EVENT_HOLIDAY, hours=_check_hours(hours), cost=0, params={"hours": hours})


async def start_drill(session: AsyncSession, emperor_id: int, hours: int) -> Started:
    _check_hours(hours)
    return await _start(
        session, emperor_id, EVENT_DRILL, hours=hours, cost=await drill_price(session, emperor_id, hours),
        params={"percent": EMPIRE_DRILL_CD_PERCENT, "hours": hours},
    )


async def start_tournament(session: AsyncSession, emperor_id: int, prize: int) -> Started:
    if prize < EMPIRE_EVENT_MIN_FUND:
        raise BadParamsError
    return await _start(
        session, emperor_id, EVENT_TOURNAMENT, hours=EMPIRE_TOURNAMENT_HOURS, cost=prize, pool=prize,
        params={"prize": prize},
    )


async def push_recipients(session: AsyncSession, emperor_id: int) -> list[int]:
    """Подданные, не выключившие сообщения императора."""
    from bot.constant.settings import NOTIFY_EMPEROR
    from bot.db.repositories.empire import list_subjects

    return [uid for uid, muted in await list_subjects(session, emperor_id, NOTIFY_EMPEROR) if not muted]


# --- подданный ---


async def subject_events(session: AsyncSession, user_id: int) -> tuple[int | None, list[tuple[EmpireEvent, bool]]]:
    """(император, [(активный ивент, можно ли забрать сейчас)])."""
    emperor = await emperor_of(session, user_id)
    if emperor is None:
        return None, []
    rows = (await session.execute(
        select(EmpireEvent).where(EmpireEvent.emperor_id == emperor, EmpireEvent.status == EVENT_ACTIVE).order_by(EmpireEvent.id)
    )).scalars().all()
    out = []
    for row in rows:
        claimable = False
        if row.kind in (EVENT_COINS, EVENT_STATISTS, EVENT_DAILY) and row.ends_at > _now():
            claimed = await session.scalar(text(
                "SELECT EXISTS(SELECT 1 FROM empire_event_claims WHERE event_id = :e AND user_id = :u AND day = :d)"
            ), {"e": row.id, "u": user_id, "d": _claim_day(row)})
            claimable = not claimed and _has_stock(row)
        out.append((row, claimable))
    return emperor, out


def _claim_day(row: EmpireEvent) -> date:
    return _now().date() if row.kind == EVENT_DAILY else row.created_at.date()


def _has_stock(row: EmpireEvent) -> bool:
    per = int(row.params.get("per", 0))
    if row.kind == EVENT_STATISTS:
        return row.slots > 0 and row.units >= per
    if row.kind == EVENT_COINS:
        return row.slots > 0 and row.pool >= per
    return row.pool >= per


@dataclass(frozen=True, slots=True)
class Claimed:
    kind: str
    amount: int
    rank: str | None = None


async def claim(session: AsyncSession, user_id: int, event_id: int) -> Claimed:
    """Забрать из раздачи / подарка. Порядок строк: игрок → ивент. Коммитит."""
    from bot.services.resource.statists import StatistKey, give_statists

    await session.execute(text("SELECT 1 FROM users WHERE id = :u FOR UPDATE"), {"u": user_id})
    row = await session.scalar(
        select(EmpireEvent).where(EmpireEvent.id == event_id).with_for_update().execution_options(populate_existing=True)
    )
    if (
        row is None or row.status != EVENT_ACTIVE or row.ends_at <= _now()
        or row.kind not in (EVENT_COINS, EVENT_STATISTS, EVENT_DAILY)
        or not await _is_subject(session, user_id, row.emperor_id)
    ):
        raise EventGoneError
    if not _has_stock(row):
        raise EventEmptyError
    inserted = await session.scalar(text(
        "INSERT INTO empire_event_claims (event_id, user_id, day) VALUES (:e, :u, :d) "
        "ON CONFLICT DO NOTHING RETURNING event_id"
    ), {"e": row.id, "u": user_id, "d": _claim_day(row)})
    if inserted is None:
        raise AlreadyClaimedError
    per = int(row.params["per"])
    row.claims += 1
    if row.kind == EVENT_STATISTS:
        row.units -= per
        row.slots -= 1
        await give_statists(session, user_id, StatistKey(rank=row.params["rank"]), per, CAMP_DEFENSE)
        await session.commit()
        return Claimed(row.kind, per, row.params["rank"])
    row.pool -= per
    row.spent += per
    if row.kind == EVENT_COINS:
        row.slots -= 1
    with coin_reason(REASON_EMPIRE_EVENT):
        await business_repo.add_coins(session, user_id, per)
    await session.commit()
    return Claimed(row.kind, per)


# --- эффекты (хуки из других доменов, НЕ коммитят) ---


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    """Доля окна [a0, a1], попавшая в [b0, b1]."""
    span = (a1 - a0).total_seconds()
    if span <= 0:
        return 0.0
    inter = (min(a1, b1) - max(a0, b0)).total_seconds()
    return max(0.0, min(1.0, inter / span))


@dataclass(frozen=True, slots=True)
class IncomeEffects:
    holiday_share: float  # доля окна начисления в налоговых каникулах
    feast_event_id: int | None
    feast_share: float  # доля окна в празднике
    feast_percent: int


async def income_effects(session: AsyncSession, emperor_id: int, since: datetime, until: datetime) -> IncomeEffects:
    rows = (await session.execute(
        select(EmpireEvent.id, EmpireEvent.kind, EmpireEvent.created_at, EmpireEvent.ends_at, EmpireEvent.params).where(
            EmpireEvent.emperor_id == emperor_id, EmpireEvent.status == EVENT_ACTIVE,
            EmpireEvent.kind.in_((EVENT_FEAST, EVENT_HOLIDAY)),
        )
    )).all()
    holiday, feast_id, feast_share, feast_percent = 0.0, None, 0.0, 0
    for event_id, kind, start, end, params in rows:
        share = _overlap(since, until, start, end)
        if kind == EVENT_HOLIDAY:
            holiday = share
        elif share > 0:
            feast_id, feast_share, feast_percent = event_id, share, int(params.get("percent", 0))
    return IncomeEffects(holiday, feast_id, feast_share, feast_percent)


async def take_feast(session: AsyncSession, event_id: int, want: int) -> int:
    """Бонус праздника — из фонда, сколько осталось (атомарно). → выплачено."""
    if want <= 0:
        return 0
    # SKIP LOCKED: PvP, трон и война начисляют доход двоим в одной транзакции — ожидание строки
    # фонда там давало бы взаимоблокировку с самим подданным, собирающим доход. Строка занята —
    # бонус за этот сбор пропускается (редко), зато никто не ждёт.
    taken = await session.scalar(text(
        "WITH e AS (SELECT id, LEAST(pool, :w) AS t FROM empire_events WHERE id = :id AND status = 'active' "
        "FOR UPDATE SKIP LOCKED) "
        "UPDATE empire_events v SET pool = v.pool - e.t, spent = v.spent + e.t FROM e WHERE v.id = e.id RETURNING e.t"
    ), {"w": want, "id": event_id})
    return int(taken or 0)


async def drill_reduction(session: AsyncSession, user_id: int) -> float:
    """Сборы императора игрока: доля сокращения КД тренировок (0 — нет)."""
    emperor = await emperor_of(session, user_id)
    if emperor is None:
        return 0.0
    percent = await session.scalar(text(
        "SELECT (params->>'percent')::int FROM empire_events WHERE emperor_id = :e AND kind = :k "
        "AND status = 'active' AND ends_at > now()"
    ), {"e": emperor, "k": EVENT_DRILL})
    return (percent or 0) / 100


# --- завершение (фон) ---


@dataclass(frozen=True, slots=True)
class Finished:
    event_id: int
    kind: str
    emperor_id: int
    spent: int
    refund: int
    claims: int
    winners: list[tuple[int, int, int]]  # турнир: (игрок, побед, приз)


_WINS_SQL = text("""
SELECT uid, count(*) AS wins FROM (
    SELECT attacker_id AS uid FROM battle_log
     WHERE created_at >= :s AND created_at < :e AND attacker_won AND defender_id IS NOT NULL
    UNION ALL
    SELECT defender_id FROM battle_log
     WHERE created_at >= :s AND created_at < :e AND NOT attacker_won AND defender_id IS NOT NULL
) w
JOIN users u ON u.id = w.uid
JOIN cities c ON c.id = u.city_id AND c.emperor_id = :emp
WHERE w.uid <> :emp
GROUP BY uid ORDER BY wins DESC, uid LIMIT :n
""")


async def _finish(session: AsyncSession, row: EmpireEvent) -> Finished:
    """Итог одного ивента: турнир — призы; остаток фонда (и статистов — деньгами) — императору."""
    winners: list[tuple[int, int, int]] = []
    if row.kind == EVENT_TOURNAMENT and row.pool > 0:
        top = (await session.execute(
            _WINS_SQL, {"s": row.created_at, "e": row.ends_at, "emp": row.emperor_id, "n": len(EMPIRE_TOURNAMENT_SHARES)}
        )).all()
        prize = int(row.params.get("prize", row.pool))
        places = list(zip(top, EMPIRE_TOURNAMENT_SHARES))  # места — по победам
        with coin_reason(REASON_EMPIRE_EVENT):
            for (uid, wins), share in sorted(places, key=lambda p: p[0][0]):  # запись строк — по id
                amount = min(row.pool, prize * share // 100)
                if amount > 0:
                    await business_repo.add_coins(session, uid, amount)
                    row.pool -= amount
                    row.spent += amount
            winners = [(int(uid), int(wins), prize * share // 100) for (uid, wins), share in places]
    refund = row.pool
    if row.kind == EVENT_STATISTS and row.units > 0:
        refund += row.units * statist_unit_price(row.params["rank"])
    if refund > 0:
        with coin_reason(REASON_EMPIRE_EVENT):
            await business_repo.add_coins(session, row.emperor_id, refund)
    row.status = EVENT_DONE
    row.result = {"refund": refund, "winners": winners}
    row.pool = 0
    row.units = 0
    return Finished(row.id, row.kind, row.emperor_id, row.spent, refund, row.claims, winners)


async def finish_due(session_factory: async_sessionmaker[AsyncSession]) -> list[Finished]:
    """Фон: закрыть истёкшие ивенты, каждый — своей транзакцией (ивент → строки игроков)."""
    async with session_factory() as session:
        ids = list((await session.scalars(
            select(EmpireEvent.id).where(EmpireEvent.status == EVENT_ACTIVE, EmpireEvent.ends_at <= _now()).limit(100)
        )).all())
    done = []
    for event_id in ids:
        try:
            async with session_factory() as session:
                row = await session.scalar(
                    select(EmpireEvent).where(EmpireEvent.id == event_id, EmpireEvent.status == EVENT_ACTIVE)
                    .with_for_update().execution_options(populate_existing=True)
                )
                if row is None:
                    continue
                done.append(await _finish(session, row))
                await session.commit()
        except Exception:
            log.exception("Empire event %s finish failed", event_id)
    return done
