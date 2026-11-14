"""Банки игроков и кредиты (сервис). Банки v2 — 2026-11-14.

Пользователь: банк создаёт игрок — капитал, срок кредита от и до (дни) и ставки. Просьба банкира-игрока, решения
пользователя через AskUserQuestion:
- два вида кредита: **фикс** (сумма + X% один раз, сколько бы ни прошло) и **почасовой** (X% каждый начавшийся час на
  остаток тела до срока). Банкир включает один или оба;
- **заявка → договор**: заёмщик подаёт заявку, владелец или участник банка одобряет (может дописать условия текстом)
  или отклоняет; заёмщику приходит договор, деньги — только после подписи. Капитал резервируется при одобрении;
- **пеня** — % в час на долг, пока идёт заморозка, не больше `BANK_PENALTY_CAP` суммы кредита;
- **участники банка** (до `BANK_MEMBERS_MAX`): пополняют капитал и одобряют заявки; забрать, условия, закрыть — владелец;
- **невозврат**: конфискация (NHCoin → статисты владельцу банка → здания) → заморозка `BANK_FREEZE_DAYS` (всё
  заблокировано, доход в долг, пеня) → **рабство**: заморозка снимается, `BANK_SLAVE_SHARE` дохода уходит банкиру, пока
  долг не закрыт (банда больше не удаляется).

Деньги: свободный капитал — `banks.capital`, выданное — `bank_loans.principal`. Платёж гасит пеню → проценты → тело и
идёт в капитал банка (банка нет — владельцу на счёт). Порядок блокировок: банк → кредит → игрок; один commit на операцию,
Redis — после commit; лок на клик снимается сразу после операции. Удержание с дохода «раба» делается внутри начисления
дохода (строка игрока уже заблокирована), поэтому кредит берётся `SKIP LOCKED`, а в капитал банка удержанное переносит
фоновый проход (`slave_pool`) — без нарушения порядка блокировок.
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import action_lock
from bot.config.bank import (
    BANK_APPLY_HOURS,
    BANK_DAY_SECONDS,
    BANK_DAYS_MAX,
    BANK_DAYS_MIN,
    BANK_FIXED_MAX,
    BANK_FIXED_MIN,
    BANK_FREEZE_DAYS,
    BANK_HOUR_SECONDS,
    BANK_HOURLY_MAX,
    BANK_HOURLY_MIN,
    BANK_MEMBERS_MAX,
    BANK_MIN_CAPITAL,
    BANK_MIN_LOAN,
    BANK_OFFER_HOURS,
    BANK_PAGE,
    BANK_PENALTY_CAP,
    BANK_PENALTY_MAX,
    BANK_SLAVE_SHARE,
    BANK_SWEEP_SECONDS,
    BANK_TERMS_MAX_LEN,
)
from bot.config.characteristic import statist_unit_power
from bot.config.contract import CONTRACT_COINS_PER_POWER
from bot.config.game import ACTION_LOCK_MS
from bot.constant.bank import (
    KIND_DAILY,
    KIND_FIXED,
    KIND_HOURLY,
    LOAN_ACTIVE,
    LOAN_CANCELLED,
    LOAN_EXPIRED,
    LOAN_FROZEN,
    LOAN_OFFERED,
    LOAN_OPEN,
    LOAN_PENDING,
    LOAN_REJECTED,
    LOAN_REPAID,
    LOAN_SLAVE,
    LOAN_WAITING,
    LOCK_ACTION_BANK,
    key_frozen,
)
from bot.constant.ledger import REASON_BANK
from bot.constant.resource import RES_COINS as RES_NH
from bot.db.models.bank import Bank, BankLoan, BankMember
from bot.db.models.user import User
from bot.services.resource import grant, spend
from bot.utils.log_context import coin_reason


class BankError(Exception):
    """Ошибка операции — код текста (`texts/bank.ERRORS`)."""

    def __init__(self, code: str, value: int | float = 0) -> None:
        super().__init__(code)
        self.code, self.value = code, value


@dataclass(frozen=True, slots=True)
class BankRow:
    id: int
    owner_id: int
    owner_name: str
    capital: int
    fixed_rate: float | None
    hourly_rate: float | None
    penalty_rate: float
    min_days: int
    max_days: int
    open_loans: int
    lent_total: int


@dataclass(frozen=True, slots=True)
class Notice:
    """Пуш: кому, код текста (`texts/bank.PUSHES`), числа; `loan_id` — для кнопок (одобрить, подписать)."""

    user_id: int
    code: str
    values: dict = field(default_factory=dict)
    loan_id: int = 0


@dataclass(frozen=True, slots=True)
class Team:
    bank: Bank
    is_owner: bool
    members: tuple[int, ...]  # id участников (без владельца)

    @property
    def ids(self) -> tuple[int, ...]:
        return (self.bank.owner_id, *self.members)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_BANK)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise BankError("busy")
    return key


def _locked(fn):
    """Лок на клик (правило 2) на всю операцию; снимается сразу после неё. Сигнатура: (session, redis, user_id, ...)."""

    @functools.wraps(fn)
    async def wrapper(session, redis, user_id, *args, **kwargs):
        key = await _lock(redis, user_id)
        try:
            return await fn(session, redis, user_id, *args, **kwargs)
        finally:
            await redis.delete(key)

    return wrapper


def check_terms(fixed: float | None, hourly: float | None, penalty: float, min_days: int, max_days: int) -> None:
    if fixed is None and hourly is None:
        raise BankError("no_kind")
    if fixed is not None and not BANK_FIXED_MIN - 1e-9 <= fixed <= BANK_FIXED_MAX + 1e-9:
        raise BankError("bad_fixed")
    if hourly is not None and not BANK_HOURLY_MIN - 1e-12 <= hourly <= BANK_HOURLY_MAX + 1e-9:
        raise BankError("bad_hourly")
    if not 0 <= penalty <= BANK_PENALTY_MAX + 1e-9:
        raise BankError("bad_penalty")
    if not BANK_DAYS_MIN <= min_days <= max_days <= BANK_DAYS_MAX:
        raise BankError("bad_days")


def kind_rate(bank: Bank, kind: str) -> float | None:
    return bank.fixed_rate if kind == KIND_FIXED else bank.hourly_rate if kind == KIND_HOURLY else None


# --- проценты и пеня ----------------------------------------------------------------------------

def accrue(loan: BankLoan, now: datetime | None = None) -> int:
    """Начислить проценты (почасовой — за начавшиеся часы, legacy — за начавшиеся сутки, до срока) и пеню (заморозка —
    за начавшиеся часы после срока, под потолком). Фикс начисляется один раз при подписи. Меняет объект. → начислено."""
    if loan.status not in LOAN_OPEN:
        return 0
    now = now or _now()
    added = 0
    elapsed = max(0.0, (min(now, loan.due_at) - loan.taken_at).total_seconds())
    if loan.kind == KIND_HOURLY:
        started = min(loan.days * 24, int(elapsed // BANK_HOUR_SECONDS) + 1)
        for _ in range(loan.accrued_hours, started):
            added += max(1, round(loan.principal * loan.rate)) if loan.principal else 0
        loan.accrued_hours = max(loan.accrued_hours, started)
    elif loan.kind == KIND_DAILY:
        started = min(loan.days, int(elapsed // BANK_DAY_SECONDS) + 1)
        for _ in range(loan.accrued_days, started):
            added += max(1, round(loan.principal * loan.rate)) if loan.principal else 0
        loan.accrued_days = max(loan.accrued_days, started)
    loan.interest += added
    if loan.status == LOAN_FROZEN and loan.penalty_rate > 0 and now > loan.due_at:
        hours = int((now - loan.due_at).total_seconds() // BANK_HOUR_SECONDS)
        cap = int(loan.amount * BANK_PENALTY_CAP)
        for _ in range(loan.penalty_hours, hours):
            step = min(max(1, round((loan.principal + loan.interest) * loan.penalty_rate)), cap - loan.penalty_total)
            if step <= 0 or not (loan.principal + loan.interest):
                break
            loan.penalty += step
            loan.penalty_total += step
            added += step
        loan.penalty_hours = max(loan.penalty_hours, hours)
    return added


def _apply_payment(loan: BankLoan, amount: int) -> tuple[int, int]:
    """Платёж: пеня → проценты → тело. → (на пеню и проценты — доход банка, на тело)."""
    to_penalty = min(amount, loan.penalty)
    to_interest = min(amount - to_penalty, loan.interest)
    to_principal = min(amount - to_penalty - to_interest, loan.principal)
    loan.penalty -= to_penalty
    loan.interest -= to_interest
    loan.principal -= to_principal
    loan.paid += to_penalty + to_interest + to_principal
    return to_penalty + to_interest, to_principal


async def _credit_lender(session: AsyncSession, loan: BankLoan, amount: int, income: int) -> None:
    """Деньги по кредиту — в капитал банка, а если банка уже нет — владельцу на счёт."""
    if amount <= 0:
        return
    if loan.bank_id is not None:
        result = await session.execute(
            update(Bank).where(Bank.id == loan.bank_id).values(capital=Bank.capital + amount, earned_total=Bank.earned_total + income)
        )
        if result.rowcount:
            return
    with coin_reason(REASON_BANK):
        await grant(session, loan.lender_id, RES_NH, amount)


def _close_if_paid(loan: BankLoan, now: datetime) -> bool:
    if loan.debt > 0:
        return False
    loan.status = LOAN_REPAID
    loan.closed_at = now
    loan.frozen_until = None
    return True


# --- банк и команда -----------------------------------------------------------------------------

async def get_bank(session: AsyncSession, owner_id: int, *, for_update: bool = False) -> Bank | None:
    stmt = select(Bank).where(Bank.owner_id == owner_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def team_of(session: AsyncSession, user_id: int, *, for_update: bool = False) -> Team | None:
    """Банк игрока: свой (владелец) или тот, где он участник."""
    bank = await get_bank(session, user_id, for_update=for_update)
    is_owner = bank is not None
    if bank is None:
        bank_id = await session.scalar(select(BankMember.bank_id).where(BankMember.user_id == user_id))
        if bank_id is None:
            return None
        stmt = select(Bank).where(Bank.id == bank_id)
        bank = await session.scalar(stmt.with_for_update() if for_update else stmt)
        if bank is None:
            return None
    members = tuple((await session.scalars(select(BankMember.user_id).where(BankMember.bank_id == bank.id).order_by(BankMember.added_at))).all())
    return Team(bank, is_owner, members)


async def _team_by_bank(session: AsyncSession, bank: Bank) -> tuple[int, ...]:
    members = (await session.scalars(select(BankMember.user_id).where(BankMember.bank_id == bank.id))).all()
    return (bank.owner_id, *members)


async def lent_out(session: AsyncSession, bank_id: int) -> tuple[int, int, int]:
    """(выдано сейчас — остаток тела, открытых кредитов, зарезервировано под неподписанные договоры)."""
    row = (await session.execute(
        select(func.coalesce(func.sum(BankLoan.principal), 0), func.count(BankLoan.id))
        .where(BankLoan.bank_id == bank_id, BankLoan.status.in_(LOAN_OPEN))
    )).one()
    reserved = await session.scalar(
        select(func.coalesce(func.sum(BankLoan.amount), 0)).where(BankLoan.bank_id == bank_id, BankLoan.status == LOAN_OFFERED)
    )
    return int(row[0]), int(row[1]), int(reserved or 0)


@_locked
async def create_bank(session: AsyncSession, redis: Redis, user_id: int, capital: int, fixed: float | None, hourly: float | None,
                      penalty: float, min_days: int, max_days: int) -> Bank:
    check_terms(fixed, hourly, penalty, min_days, max_days)
    if capital < BANK_MIN_CAPITAL:
        raise BankError("min_capital", BANK_MIN_CAPITAL)
    if await team_of(session, user_id) is not None:
        raise BankError("has_bank")
    with coin_reason(REASON_BANK):
        if not await spend(session, user_id, RES_NH, capital):
            await session.rollback()
            raise BankError("no_money", capital)
    bank = Bank(owner_id=user_id, capital=capital, rate=None, fixed_rate=fixed, hourly_rate=hourly, penalty_rate=penalty,
                min_days=min_days, max_days=max_days, lent_total=0, earned_total=0)
    session.add(bank)
    await session.commit()
    return bank


@_locked
async def add_capital(session: AsyncSession, redis: Redis, user_id: int, amount: int) -> int:
    """Пополнить капитал — владелец или участник."""
    if amount <= 0:
        raise BankError("bad_amount")
    team = await team_of(session, user_id, for_update=True)
    if team is None:
        raise BankError("no_bank")
    with coin_reason(REASON_BANK):
        if not await spend(session, user_id, RES_NH, amount):
            await session.rollback()
            raise BankError("no_money", amount)
    team.bank.capital += amount
    capital = team.bank.capital
    await session.commit()
    return capital


async def _own(session: AsyncSession, user_id: int) -> Bank:
    bank = await get_bank(session, user_id, for_update=True)
    if bank is None:
        if await team_of(session, user_id) is not None:
            raise BankError("owner_only")
        raise BankError("no_bank")
    return bank


@_locked
async def withdraw(session: AsyncSession, redis: Redis, user_id: int, amount: int) -> int:
    if amount <= 0:
        raise BankError("bad_amount")
    bank = await _own(session, user_id)
    if amount > bank.capital:
        free = bank.capital
        await session.rollback()
        raise BankError("no_capital", free)
    bank.capital -= amount
    capital = bank.capital
    with coin_reason(REASON_BANK):
        await grant(session, user_id, RES_NH, amount)
    await session.commit()
    return capital


@_locked
async def set_terms(session: AsyncSession, redis: Redis, user_id: int, fixed: float | None, hourly: float | None, penalty: float,
                    min_days: int, max_days: int) -> None:
    """Новые условия — только для новых заявок; поданные и выданные живут по своим."""
    check_terms(fixed, hourly, penalty, min_days, max_days)
    bank = await _own(session, user_id)
    bank.fixed_rate, bank.hourly_rate, bank.penalty_rate, bank.min_days, bank.max_days = fixed, hourly, penalty, min_days, max_days
    await session.commit()


@_locked
async def close_bank(session: AsyncSession, redis: Redis, user_id: int) -> int:
    """Закрыть банк: без открытых кредитов и заявок, свободный капитал — владельцу. → возвращено."""
    bank = await _own(session, user_id)
    busy = await session.scalar(
        select(func.count(BankLoan.id)).where(BankLoan.bank_id == bank.id, BankLoan.status.in_(LOAN_OPEN + LOAN_WAITING))
    )
    if busy:
        await session.rollback()
        raise BankError("has_loans")
    capital = bank.capital
    await session.delete(bank)
    with coin_reason(REASON_BANK):
        await grant(session, user_id, RES_NH, capital)
    await session.commit()
    return capital


@_locked
async def add_member(session: AsyncSession, redis: Redis, user_id: int, username: str) -> tuple[int, str]:
    """Владелец добавляет участника по @нику. → (id, ник)."""
    from bot.db.repositories.user import find_by_username
    from bot.db.models.gang import Gang

    bank = await _own(session, user_id)
    target = await find_by_username(session, username.strip().lstrip("@"))
    if target is None or not await session.scalar(select(Gang.user_id).where(Gang.user_id == target.id)):
        await session.rollback()
        raise BankError("no_player")
    if target.id == user_id:
        await session.rollback()
        raise BankError("self_member")
    if await get_bank(session, target.id) is not None or await session.scalar(select(BankMember.bank_id).where(BankMember.user_id == target.id)):
        await session.rollback()
        raise BankError("in_bank")
    count = await session.scalar(select(func.count()).select_from(BankMember).where(BankMember.bank_id == bank.id))
    if count >= BANK_MEMBERS_MAX:
        await session.rollback()
        raise BankError("members_full", BANK_MEMBERS_MAX)
    session.add(BankMember(bank_id=bank.id, user_id=target.id))
    name = target.username or str(target.id)
    await session.commit()
    return target.id, name


@_locked
async def remove_member(session: AsyncSession, redis: Redis, user_id: int, member_id: int) -> None:
    bank = await _own(session, user_id)
    await session.execute(delete(BankMember).where(BankMember.bank_id == bank.id, BankMember.user_id == member_id))
    await session.commit()


async def leave_bank(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(BankMember).where(BankMember.user_id == user_id))
    await session.commit()


# --- список банков, заявки, кредиты -------------------------------------------------------------

def _row(b: Bank, name: str | None, n: int) -> BankRow:
    return BankRow(b.id, b.owner_id, name or "—", b.capital, b.fixed_rate, b.hourly_rate, b.penalty_rate or 0.0, b.min_days, b.max_days,
                   int(n), b.lent_total)


async def list_banks(session: AsyncSession, viewer_id: int, page: int) -> tuple[list[BankRow], bool]:
    """Банки с капиталом от минимального кредита, свой (и тот, где участник) — не показываются. Сначала крупные."""
    from bot.db.models.gang import Gang

    loans = (
        select(BankLoan.bank_id, func.count(BankLoan.id).label("n"))
        .where(BankLoan.status.in_(LOAN_OPEN)).group_by(BankLoan.bank_id).subquery()
    )
    member_bank = select(BankMember.bank_id).where(BankMember.user_id == viewer_id).scalar_subquery()
    rows = (await session.execute(
        select(Bank, Gang.name, func.coalesce(loans.c.n, 0))
        .join(Gang, Gang.user_id == Bank.owner_id, isouter=True)
        .join(loans, loans.c.bank_id == Bank.id, isouter=True)
        .where(Bank.owner_id != viewer_id, Bank.id.is_distinct_from(member_bank), Bank.capital >= BANK_MIN_LOAN,
               (Bank.fixed_rate.is_not(None)) | (Bank.hourly_rate.is_not(None)))
        .order_by(Bank.capital.desc(), Bank.id)
        .offset(page * BANK_PAGE).limit(BANK_PAGE + 1)
    )).all()
    out = [_row(b, name, n) for b, name, n in rows]
    return out[:BANK_PAGE], len(out) > BANK_PAGE


async def bank_card(session: AsyncSession, bank_id: int) -> BankRow | None:
    from bot.db.models.gang import Gang

    row = (await session.execute(select(Bank, Gang.name).join(Gang, Gang.user_id == Bank.owner_id, isouter=True).where(Bank.id == bank_id))).first()
    if row is None:
        return None
    b, name = row
    _, n, _ = await lent_out(session, b.id)
    return _row(b, name, n)


async def my_loans(session: AsyncSession, user_id: int) -> list[BankLoan]:
    """Кредиты и заявки заёмщика с процентами на сейчас (без записи: проценты запишет платёж или проход)."""
    loans = list((await session.scalars(
        select(BankLoan).where(BankLoan.borrower_id == user_id, BankLoan.status.in_(LOAN_OPEN + LOAN_WAITING))
        .order_by(BankLoan.status, BankLoan.due_at)
    )).all())
    now = _now()
    for loan in loans:
        session.expunge(loan)
        accrue(loan, now)
    return loans


async def team_loans(session: AsyncSession, bank_id: int) -> list[BankLoan]:
    """Заявки, договоры и кредиты банка (для команды банка)."""
    loans = list((await session.scalars(
        select(BankLoan).where(BankLoan.bank_id == bank_id, BankLoan.status.in_(LOAN_WAITING + LOAN_OPEN)).order_by(BankLoan.status, BankLoan.id)
    )).all())
    now = _now()
    for loan in loans:
        session.expunge(loan)
        accrue(loan, now)
    return loans


async def is_frozen(redis: Redis, user_id: int) -> bool:
    return bool(await redis.exists(key_frozen(user_id)))


async def _blocked(session: AsyncSession, user_id: int) -> str | None:
    """Должник с замороженным долгом или в рабстве новых кредитов не получает."""
    status = await session.scalar(
        select(BankLoan.status).where(BankLoan.borrower_id == user_id, BankLoan.status.in_((LOAN_FROZEN, LOAN_SLAVE))).limit(1)
    )
    return "frozen" if status == LOAN_FROZEN else "slave" if status == LOAN_SLAVE else None


@_locked
async def apply_loan(session: AsyncSession, redis: Redis, user_id: int, bank_id: int, kind: str, amount: int, days: int) -> tuple[BankLoan, list[Notice]]:
    """Заявка на кредит. Деньги не двигаются — банк ещё должен одобрить."""
    if amount < BANK_MIN_LOAN:
        raise BankError("min_loan", BANK_MIN_LOAN)
    blocked = await _blocked(session, user_id)
    if blocked:
        raise BankError(blocked)
    bank = await session.scalar(select(Bank).where(Bank.id == bank_id))
    if bank is None:
        raise BankError("no_bank")
    team = await _team_by_bank(session, bank)
    if user_id in team:
        raise BankError("own_bank")
    rate = kind_rate(bank, kind)
    if rate is None:
        raise BankError("no_kind_here")
    if not bank.min_days <= days <= bank.max_days:
        raise BankError("bad_days")
    if amount > bank.capital:
        raise BankError("no_capital", bank.capital)
    has = await session.scalar(
        select(func.count(BankLoan.id)).where(BankLoan.borrower_id == user_id, BankLoan.bank_id == bank_id, BankLoan.status.in_(LOAN_OPEN + LOAN_WAITING))
    )
    if has:
        raise BankError("has_loan")
    now = _now()
    loan = BankLoan(
        bank_id=bank.id, lender_id=bank.owner_id, borrower_id=user_id, kind=kind, amount=amount, principal=amount, interest=0, penalty=0,
        penalty_total=0, paid=0, rate=rate, penalty_rate=bank.penalty_rate or 0.0, days=days, status=LOAN_PENDING, taken_at=now,
        due_at=now + timedelta(days=days), accrued_days=0, accrued_hours=0, penalty_hours=0, slave_pool=0,
    )
    session.add(loan)
    await session.commit()
    return loan, [Notice(uid, "apply", {}, loan.id) for uid in team]


async def _team_loan(session: AsyncSession, user_id: int, loan_id: int, status: str) -> tuple[BankLoan, Bank]:
    """Кредит банка, где игрок — владелец или участник, в статусе `status`; банк и кредит под блокировкой."""
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id))
    if loan is None or loan.bank_id is None or loan.status != status:
        raise BankError("no_app")
    bank = await session.scalar(select(Bank).where(Bank.id == loan.bank_id).with_for_update())
    if bank is None or user_id not in await _team_by_bank(session, bank):
        await session.rollback()
        raise BankError("no_app")
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id).with_for_update().execution_options(populate_existing=True))
    if loan.status != status:
        await session.rollback()
        raise BankError("no_app")
    return loan, bank


@_locked
async def approve(session: AsyncSession, redis: Redis, user_id: int, loan_id: int, terms: str | None = None) -> tuple[BankLoan, list[Notice]]:
    """Одобрить заявку: капитал резервируется, заёмщику уходит договор на подпись."""
    loan, bank = await _team_loan(session, user_id, loan_id, LOAN_PENDING)
    if loan.amount > bank.capital:
        free = bank.capital
        await session.rollback()
        raise BankError("no_capital", free)
    bank.capital -= loan.amount
    loan.status = LOAN_OFFERED
    loan.approved_by = user_id
    loan.terms = (terms or "").strip()[:BANK_TERMS_MAX_LEN] or None
    loan.offer_until = _now() + timedelta(hours=BANK_OFFER_HOURS)
    await session.commit()
    team = await _team_by_bank(session, bank)
    return loan, [Notice(loan.borrower_id, "offer", {}, loan.id)] + [Notice(uid, "approved", {"by": user_id}, loan.id) for uid in team if uid != user_id]


@_locked
async def reject(session: AsyncSession, redis: Redis, user_id: int, loan_id: int) -> list[Notice]:
    loan, _ = await _team_loan(session, user_id, loan_id, LOAN_PENDING)
    loan.status = LOAN_REJECTED
    loan.closed_at = _now()
    await session.commit()
    return [Notice(loan.borrower_id, "rejected", {}, loan.id)]


async def _borrower_loan(session: AsyncSession, user_id: int, loan_id: int, statuses: tuple[str, ...]) -> tuple[BankLoan, Bank | None]:
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id))
    if loan is None or loan.borrower_id != user_id or loan.status not in statuses:
        raise BankError("no_loan")
    bank = None
    if loan.bank_id is not None:  # порядок блокировок: банк → кредит → игрок
        bank = await session.scalar(select(Bank).where(Bank.id == loan.bank_id).with_for_update())
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id).with_for_update().execution_options(populate_existing=True))
    if loan.status not in statuses:
        await session.rollback()
        raise BankError("no_loan")
    return loan, bank


@_locked
async def cancel(session: AsyncSession, redis: Redis, user_id: int, loan_id: int) -> None:
    """Отозвать свою заявку, пока банк не ответил."""
    loan, _ = await _borrower_loan(session, user_id, loan_id, (LOAN_PENDING,))
    loan.status = LOAN_CANCELLED
    loan.closed_at = _now()
    await session.commit()


@_locked
async def sign(session: AsyncSession, redis: Redis, user_id: int, loan_id: int) -> tuple[BankLoan, list[Notice]]:
    """Подписать договор: деньги заёмщику, срок и проценты — с этой минуты."""
    loan, bank = await _borrower_loan(session, user_id, loan_id, (LOAN_OFFERED,))
    now = _now()
    if loan.offer_until is not None and loan.offer_until <= now:
        await session.rollback()
        raise BankError("offer_expired")
    blocked = await _blocked(session, user_id)
    if blocked:
        await session.rollback()
        raise BankError(blocked)
    loan.status = LOAN_ACTIVE
    loan.taken_at = now
    loan.due_at = now + timedelta(days=loan.days)
    if loan.kind == KIND_FIXED:
        loan.interest = max(1, round(loan.amount * loan.rate))
    accrue(loan, now)  # почасовой: первый час — сразу
    if bank is not None:
        bank.lent_total += loan.amount
    with coin_reason(REASON_BANK):
        await grant(session, user_id, RES_NH, loan.amount)
    await session.commit()
    team = await _team_by_bank(session, bank) if bank is not None else (loan.lender_id,)
    return loan, [Notice(uid, "signed", {"amount": loan.amount}, loan.id) for uid in team]


@_locked
async def decline(session: AsyncSession, redis: Redis, user_id: int, loan_id: int) -> list[Notice]:
    """Отказаться от договора — резерв возвращается в капитал."""
    loan, bank = await _borrower_loan(session, user_id, loan_id, (LOAN_OFFERED,))
    loan.status = LOAN_CANCELLED
    loan.closed_at = _now()
    if bank is not None:
        bank.capital += loan.amount
    await session.commit()
    team = await _team_by_bank(session, bank) if bank is not None else (loan.lender_id,)
    return [Notice(uid, "declined", {"amount": loan.amount}, loan.id) for uid in team]


@_locked
async def repay(session: AsyncSession, redis: Redis, user_id: int, loan_id: int, amount: int | None) -> tuple[BankLoan, int, bool]:
    """Погасить часть (`amount`) или весь долг (`None`). Замороженный долг тоже гасится здесь — заморозка снимается.
    → (кредит, погашено, разморожен)."""
    loan, _ = await _borrower_loan(session, user_id, loan_id, LOAN_OPEN)
    now = _now()
    accrue(loan, now)
    pay = loan.debt if amount is None else min(amount, loan.debt)
    if pay <= 0:
        await session.rollback()
        raise BankError("bad_amount")
    with coin_reason(REASON_BANK):
        if not await spend(session, user_id, RES_NH, pay):
            await session.rollback()
            raise BankError("no_money", pay)
    income, body = _apply_payment(loan, pay)
    await _credit_lender(session, loan, income + body, income)
    was_frozen = loan.status == LOAN_FROZEN
    closed = _close_if_paid(loan, now)
    await session.commit()
    if closed and was_frozen:
        await _refresh_frozen(session, redis, user_id)
    return loan, pay, closed and was_frozen


async def _refresh_frozen(session: AsyncSession, redis: Redis, user_id: int) -> None:
    left = await session.scalar(select(func.count(BankLoan.id)).where(BankLoan.borrower_id == user_id, BankLoan.status == LOAN_FROZEN))
    if left:
        await redis.set(key_frozen(user_id), "1", ex=BANK_SWEEP_SECONDS * 3)
    else:
        await redis.delete(key_frozen(user_id))


# --- рабство: удержание с дохода ---------------------------------------------------------------

async def slave_cut(session: AsyncSession, user_id: int, income: int) -> int:
    """Вызывается из начисления дохода (`services/business.accrue`, строка игрока уже под блокировкой): `BANK_SLAVE_SHARE`
    дохода — в счёт долга «раба». Кредит берётся `SKIP LOCKED` (занят платежом — удержим в следующий раз), деньги
    копятся в `slave_pool`, в капитал банка их переносит фоновый проход. → удержано."""
    if income <= 0:
        return 0
    loan = await session.scalar(
        select(BankLoan).where(BankLoan.borrower_id == user_id, BankLoan.status == LOAN_SLAVE).order_by(BankLoan.id).limit(1)
        .with_for_update(skip_locked=True)
    )
    if loan is None:
        return 0
    cut = min(int(income * BANK_SLAVE_SHARE), loan.debt)
    if cut <= 0:
        return 0
    with coin_reason(REASON_BANK):
        if not await spend(session, user_id, RES_NH, cut):
            return 0
    _apply_payment(loan, cut)
    loan.slave_pool += cut
    _close_if_paid(loan, _now())
    return cut


# --- просрочки: конфискация, заморозка, рабство --------------------------------------------------

async def _take_coins(session: AsyncSession, user_id: int, need: int) -> int:
    coins = await session.scalar(select(User.nh_coins).where(User.id == user_id).with_for_update()) or 0
    take = min(max(0, coins), need)
    if take:
        with coin_reason(REASON_BANK):
            await spend(session, user_id, RES_NH, take)
    return take


async def _take_statists(session: AsyncSession, user_id: int, lender_id: int, need: int) -> int:
    """Статисты с самых слабых переходят владельцу банка (засчитываются по мощи × цене мощи наёмников). Именно переходят,
    а не продаются — иначе через свой банк на твинке бесплатные статисты превращались бы в NHCoin."""
    from bot.db.repositories.extra import add_to_stacks, list_stacks, stack_key

    stacks = sorted(
        ((s, statist_unit_power(s.rank, s.stars, s.training_level, s.school, s.school_level) * CONTRACT_COINS_PER_POWER)
         for s in await list_stacks(session, user_id, for_update=True)),
        key=lambda t: t[1],
    )
    got, deltas = 0, {}
    for s, value in stacks:
        if got >= need:
            break
        value = max(1.0, value)
        n = min(s.quantity, math.ceil((need - got) / value))
        if n <= 0:
            continue
        deltas[stack_key(user_id, s.camp, s.rank, s.stars, s.training_level, s.school, s.school_level)] = -n
        lender_key = stack_key(lender_id, s.camp, s.rank, s.stars, s.training_level, s.school, s.school_level)
        deltas[lender_key] = deltas.get(lender_key, 0) + n
        got += min(need - got, int(n * value))
    await add_to_stacks(session, deltas)
    return got


async def _take_buildings(session: AsyncSession, user_id: int, need: int) -> int:
    """Здания с самых дешёвых, по цене постройки. Перед сносом доход начисляется по старому набору."""
    from bot.config.game import BUSINESS_BUILD_COST
    from bot.services.business import accrue as accrue_income

    await accrue_income(session, user_id)
    rows = (await session.execute(text(
        "SELECT b.type, count(*) FROM businesses b JOIN districts d ON d.id = b.district_id WHERE d.owner_id = :u GROUP BY b.type"
    ), {"u": user_id})).all()
    got = 0
    for type_, count in sorted(rows, key=lambda r: BUSINESS_BUILD_COST.get(r[0], 0)):
        if got >= need:
            break
        price = max(1, BUSINESS_BUILD_COST.get(type_, 1))
        n = min(int(count), math.ceil((need - got) / price))
        await session.execute(text(
            "DELETE FROM businesses WHERE id IN (SELECT b.id FROM businesses b JOIN districts d ON d.id = b.district_id "
            "WHERE d.owner_id = :u AND b.type = :t ORDER BY b.id LIMIT :n)"
        ), {"u": user_id, "t": type_, "n": n})
        got += min(need - got, n * price)
    return got


async def _collect(session: AsyncSession, loan: BankLoan, amount: int, *, coins: bool = True) -> None:
    """Засчитать конфискованное в долг. `coins=False` — статисты: они уже у владельца, монет банку не идёт."""
    if amount <= 0:
        return
    income, body = _apply_payment(loan, amount)
    if coins:
        await _credit_lender(session, loan, income + body, income)


async def _process(session: AsyncSession, loan_id: int, now: datetime) -> list[Notice]:
    """Один кредит/заявка — в своей транзакции. → пуши."""
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id))
    if loan is None:
        return []
    bank = None
    if loan.bank_id is not None:
        bank = await session.scalar(select(Bank).where(Bank.id == loan.bank_id).with_for_update())
    loan = await session.scalar(
        select(BankLoan).where(BankLoan.id == loan_id).with_for_update(skip_locked=True).execution_options(populate_existing=True)
    )
    if loan is None:
        await session.rollback()
        return []
    notices: list[Notice] = []
    who = loan.borrower_id
    changed = loan.slave_pool > 0
    if loan.slave_pool > 0:  # удержанное с дохода «раба» — в капитал банка
        pool, loan.slave_pool = loan.slave_pool, 0
        await _credit_lender(session, loan, pool, 0)
        if loan.status == LOAN_REPAID:
            notices += [Notice(who, "slave_free", {}), Notice(loan.lender_id, "lender_slave_paid", {})]
    if loan.status == LOAN_PENDING and loan.taken_at + timedelta(hours=BANK_APPLY_HOURS) <= now:
        loan.status, loan.closed_at = LOAN_EXPIRED, now
        notices.append(Notice(who, "app_expired", {}, loan.id))
    elif loan.status == LOAN_OFFERED and loan.offer_until is not None and loan.offer_until <= now:
        loan.status, loan.closed_at = LOAN_EXPIRED, now
        if bank is not None:
            bank.capital += loan.amount
        notices.append(Notice(who, "offer_expired", {}, loan.id))
    elif loan.status == LOAN_ACTIVE and loan.due_at <= now:
        accrue(loan, now)
        debt = loan.debt
        coins = await _take_coins(session, who, debt)
        await _collect(session, loan, coins)
        statists = await _take_statists(session, who, loan.lender_id, loan.debt) if loan.debt else 0
        await _collect(session, loan, statists, coins=False)
        buildings = await _take_buildings(session, who, loan.debt) if loan.debt else 0
        await _collect(session, loan, buildings)
        taken = {"debt": debt, "coins": coins, "statists": statists, "buildings": buildings, "left": loan.debt}
        if _close_if_paid(loan, now):
            notices += [Notice(who, "seized", taken), Notice(loan.lender_id, "lender_seized", taken)]
        else:
            loan.status = LOAN_FROZEN
            loan.frozen_until = now + timedelta(days=BANK_FREEZE_DAYS)
            taken["days"] = BANK_FREEZE_DAYS
            notices += [Notice(who, "frozen", taken), Notice(loan.lender_id, "lender_frozen", taken)]
    elif loan.status == LOAN_FROZEN:  # весь доход — в долг, капает пеня
        from bot.services.business import accrue as accrue_income

        accrue(loan, now)
        await accrue_income(session, who)
        coins = await _take_coins(session, who, loan.debt)
        await _collect(session, loan, coins)
        if _close_if_paid(loan, now):
            notices += [Notice(who, "unfrozen", {}), Notice(loan.lender_id, "lender_repaid", {"amount": loan.paid})]
        elif loan.frozen_until is not None and loan.frozen_until <= now:
            loan.status = LOAN_SLAVE
            loan.frozen_until = None
            share = round(BANK_SLAVE_SHARE * 100)
            notices += [Notice(who, "slave", {"left": loan.debt, "share": share}), Notice(loan.lender_id, "lender_slave", {"left": loan.debt, "share": share})]
    elif not changed:
        await session.rollback()
        return []
    await session.commit()
    return notices


async def sweep(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> list[Notice]:
    """Фоновый проход (`main.py`): сгоревшие заявки и договоры, просрочки → конфискация/заморозка, заморозка → доход в
    долг/рабство, удержанное с «рабов» → в капитал. Флаги заморозки в Redis выставляются заново каждый проход."""
    now = _now()
    async with session_factory() as session:
        ids = list((await session.scalars(
            select(BankLoan.id).where(
                (BankLoan.status.in_(LOAN_WAITING))
                | ((BankLoan.status == LOAN_ACTIVE) & (BankLoan.due_at <= now))
                | (BankLoan.status == LOAN_FROZEN)
                | (BankLoan.slave_pool > 0)
            ).order_by(BankLoan.id)
        )).all())
    notices: list[Notice] = []
    for loan_id in ids:
        async with session_factory() as session:
            notices += await _process(session, loan_id, now)
    async with session_factory() as session:
        frozen = set((await session.scalars(select(BankLoan.borrower_id).where(BankLoan.status == LOAN_FROZEN))).all())
    for user_id in frozen:
        await redis.set(key_frozen(user_id), "1", ex=BANK_SWEEP_SECONDS * 3)
    for n in notices:
        if n.code in ("unfrozen", "slave") and n.user_id not in frozen:
            await redis.delete(key_frozen(n.user_id))
    return notices
