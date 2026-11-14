"""Банки игроков и кредиты (сервис).

Пользователь 2026-11-14: банк создаёт игрок — капитал, срок кредита от и до (дни), процент в день, который капает
ему. Остальные банды выбирают банк в списке и берут кредит, гасят частями. Невозврат к сроку: конфискация владельцу
банка (NHCoin → статисты по цене мощи в магазине наёмников → здания по цене постройки), не хватило — заморозка банды
на `BANK_FREEZE_DAYS` (действия заблокированы, доход уходит в долг), не погасил — удаление банды, остаток списан.

Деньги: капитал лежит в `banks.capital`, выданное — в `bank_loans.principal`. Проценты капают раз в сутки на остаток
тела, первые сутки — сразу при выдаче (иначе кредит на час был бы бесплатным). Платёж гасит сначала проценты, потом
тело, и уходит в капитал банка (банк закрыт — владельцу на счёт). Порядок блокировок везде один: банк → кредит →
игрок; один commit на операцию (правило 10), Redis — после commit; лок на клик (правило 2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import action_lock
from bot.config.bank import (
    BANK_DAY_SECONDS,
    BANK_DAYS_MAX,
    BANK_DAYS_MIN,
    BANK_FREEZE_DAYS,
    BANK_MIN_CAPITAL,
    BANK_MIN_LOAN,
    BANK_PAGE,
    BANK_RATE_MAX,
    BANK_RATE_MIN,
    BANK_SWEEP_SECONDS,
)
from bot.config.characteristic import statist_unit_power
from bot.config.contract import CONTRACT_COINS_PER_POWER
from bot.config.game import ACTION_LOCK_MS
from bot.constant.bank import (
    LOAN_ACTIVE,
    LOAN_DEFAULTED,
    LOAN_FROZEN,
    LOAN_OPEN,
    LOAN_REPAID,
    LOCK_ACTION_BANK,
    key_frozen,
)
from bot.constant.ledger import REASON_BANK
from bot.constant.resource import RES_COINS as RES_NH
from bot.db.models.bank import Bank, BankLoan
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
    rate: float
    min_days: int
    max_days: int
    open_loans: int
    lent_total: int


@dataclass(frozen=True, slots=True)
class Notice:
    """Пуш после прохода: кому и какой текст (код `texts/bank.PUSHES` + числа)."""

    user_id: int
    code: str
    values: dict


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_BANK)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise BankError("busy")
    return key


def _check_terms(rate: float, min_days: int, max_days: int) -> None:
    if not BANK_RATE_MIN - 1e-9 <= rate <= BANK_RATE_MAX + 1e-9:
        raise BankError("bad_rate")
    if not BANK_DAYS_MIN <= min_days <= max_days <= BANK_DAYS_MAX:
        raise BankError("bad_days")


# --- проценты ----------------------------------------------------------------------------------

def accrue(loan: BankLoan, now: datetime | None = None) -> int:
    """Начислить проценты за начавшиеся сутки (не больше срока кредита). Меняет объект, НЕ пишет сам. → начислено."""
    now = now or _now()
    elapsed = (min(now, loan.due_at) - loan.taken_at).total_seconds()
    started = min(loan.days, int(max(0.0, elapsed) // BANK_DAY_SECONDS) + 1)
    added = 0
    for _ in range(loan.accrued_days, started):
        added += max(1, round(loan.principal * loan.rate)) if loan.principal else 0
    if started > loan.accrued_days:
        loan.accrued_days = started
        loan.interest += added
    return added


def _apply_payment(loan: BankLoan, amount: int) -> tuple[int, int]:
    """Платёж по кредиту: сначала проценты, потом тело. → (на проценты, на тело)."""
    to_interest = min(amount, loan.interest)
    to_principal = min(amount - to_interest, loan.principal)
    loan.interest -= to_interest
    loan.principal -= to_principal
    loan.paid += to_interest + to_principal
    return to_interest, to_principal


async def _credit_lender(session: AsyncSession, loan: BankLoan, amount: int, interest: int) -> None:
    """Деньги по кредиту — в капитал банка, а если банка уже нет — владельцу на счёт."""
    if amount <= 0:
        return
    if loan.bank_id is not None:
        result = await session.execute(
            update(Bank).where(Bank.id == loan.bank_id)
            .values(capital=Bank.capital + amount, earned_total=Bank.earned_total + interest)
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


# --- банк владельца -----------------------------------------------------------------------------

async def get_bank(session: AsyncSession, owner_id: int, *, for_update: bool = False) -> Bank | None:
    stmt = select(Bank).where(Bank.owner_id == owner_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def lent_out(session: AsyncSession, bank_id: int) -> tuple[int, int]:
    """(выдано сейчас — остаток тела, кредитов открыто) по банку."""
    row = (await session.execute(
        select(func.coalesce(func.sum(BankLoan.principal), 0), func.count(BankLoan.id))
        .where(BankLoan.bank_id == bank_id, BankLoan.status.in_(LOAN_OPEN))
    )).one()
    return int(row[0]), int(row[1])


async def create_bank(session: AsyncSession, redis: Redis, user_id: int, capital: int, rate: float, min_days: int, max_days: int) -> Bank:
    _check_terms(rate, min_days, max_days)
    if capital < BANK_MIN_CAPITAL:
        raise BankError("min_capital", BANK_MIN_CAPITAL)
    await _lock(redis, user_id)
    if await get_bank(session, user_id) is not None:
        raise BankError("has_bank")
    with coin_reason(REASON_BANK):
        if not await spend(session, user_id, RES_NH, capital):
            await session.rollback()
            raise BankError("no_money", capital)
    bank = Bank(owner_id=user_id, capital=capital, rate=rate, min_days=min_days, max_days=max_days)
    session.add(bank)
    await session.commit()
    return bank


async def add_capital(session: AsyncSession, redis: Redis, user_id: int, amount: int) -> int:
    if amount <= 0:
        raise BankError("bad_amount")
    await _lock(redis, user_id)
    bank = await get_bank(session, user_id, for_update=True)
    if bank is None:
        raise BankError("no_bank")
    with coin_reason(REASON_BANK):
        if not await spend(session, user_id, RES_NH, amount):
            await session.rollback()
            raise BankError("no_money", amount)
    bank.capital += amount
    await session.commit()
    return bank.capital


async def withdraw(session: AsyncSession, redis: Redis, user_id: int, amount: int) -> int:
    if amount <= 0:
        raise BankError("bad_amount")
    await _lock(redis, user_id)
    bank = await get_bank(session, user_id, for_update=True)
    if bank is None:
        raise BankError("no_bank")
    if amount > bank.capital:
        free = bank.capital  # до rollback: после него объект истёк
        await session.rollback()
        raise BankError("no_capital", free)
    bank.capital -= amount
    with coin_reason(REASON_BANK):
        await grant(session, user_id, RES_NH, amount)
    await session.commit()
    return bank.capital


async def set_terms(session: AsyncSession, redis: Redis, user_id: int, rate: float, min_days: int, max_days: int) -> None:
    """Новые условия — только для новых кредитов; выданные живут по своим."""
    _check_terms(rate, min_days, max_days)
    await _lock(redis, user_id)
    bank = await get_bank(session, user_id, for_update=True)
    if bank is None:
        raise BankError("no_bank")
    bank.rate, bank.min_days, bank.max_days = rate, min_days, max_days
    await session.commit()


async def close_bank(session: AsyncSession, redis: Redis, user_id: int) -> int:
    """Закрыть банк: только без открытых кредитов, свободный капитал — владельцу. → возвращено."""
    await _lock(redis, user_id)
    bank = await get_bank(session, user_id, for_update=True)
    if bank is None:
        raise BankError("no_bank")
    if (await lent_out(session, bank.id))[1]:
        await session.rollback()
        raise BankError("has_loans")
    capital = bank.capital
    await session.delete(bank)
    with coin_reason(REASON_BANK):
        await grant(session, user_id, RES_NH, capital)
    await session.commit()
    return capital


# --- список банков и кредиты заёмщика ------------------------------------------------------------

async def list_banks(session: AsyncSession, viewer_id: int, page: int) -> tuple[list[BankRow], bool]:
    """Банки с капиталом от минимального кредита, сначала дешёвые. Свой банк в списке не показывается."""
    from bot.db.models.gang import Gang

    loans = (
        select(BankLoan.bank_id, func.count(BankLoan.id).label("n"))
        .where(BankLoan.status.in_(LOAN_OPEN)).group_by(BankLoan.bank_id).subquery()
    )
    rows = (await session.execute(
        select(Bank, Gang.name, func.coalesce(loans.c.n, 0))
        .join(Gang, Gang.user_id == Bank.owner_id, isouter=True)
        .join(loans, loans.c.bank_id == Bank.id, isouter=True)
        .where(Bank.owner_id != viewer_id, Bank.capital >= BANK_MIN_LOAN)
        .order_by(Bank.rate, Bank.capital.desc(), Bank.id)
        .offset(page * BANK_PAGE).limit(BANK_PAGE + 1)
    )).all()
    out = [BankRow(b.id, b.owner_id, name or "—", b.capital, b.rate, b.min_days, b.max_days, int(n), b.lent_total) for b, name, n in rows]
    return out[:BANK_PAGE], len(out) > BANK_PAGE


async def bank_card(session: AsyncSession, bank_id: int) -> BankRow | None:
    from bot.db.models.gang import Gang

    row = (await session.execute(select(Bank, Gang.name).join(Gang, Gang.user_id == Bank.owner_id, isouter=True).where(Bank.id == bank_id))).first()
    if row is None:
        return None
    b, name = row
    _, n = await lent_out(session, b.id)
    return BankRow(b.id, b.owner_id, name or "—", b.capital, b.rate, b.min_days, b.max_days, n, b.lent_total)


async def my_loans(session: AsyncSession, user_id: int) -> list[BankLoan]:
    """Открытые кредиты заёмщика с процентами на сейчас (без записи — запишется при платеже/проходе)."""
    loans = list((await session.scalars(
        select(BankLoan).where(BankLoan.borrower_id == user_id, BankLoan.status.in_(LOAN_OPEN)).order_by(BankLoan.due_at)
    )).all())
    now = _now()
    for loan in loans:
        session.expunge(loan)  # проценты на экране — только показ, в БД их запишет платёж или проход
        accrue(loan, now)
    return loans


async def issued_loans(session: AsyncSession, owner_id: int) -> list[BankLoan]:
    """Открытые кредиты, выданные банком владельца."""
    return list((await session.scalars(
        select(BankLoan).where(BankLoan.lender_id == owner_id, BankLoan.status.in_(LOAN_OPEN)).order_by(BankLoan.due_at)
    )).all())


async def frozen_debt(session: AsyncSession, user_id: int) -> BankLoan | None:
    return await session.scalar(
        select(BankLoan).where(BankLoan.borrower_id == user_id, BankLoan.status == LOAN_FROZEN).order_by(BankLoan.frozen_until)
    )


async def is_frozen(redis: Redis, user_id: int) -> bool:
    return bool(await redis.exists(key_frozen(user_id)))


async def take_loan(session: AsyncSession, redis: Redis, user_id: int, bank_id: int, amount: int, days: int) -> BankLoan:
    if amount < BANK_MIN_LOAN:
        raise BankError("min_loan", BANK_MIN_LOAN)
    await _lock(redis, user_id)
    if await is_frozen(redis, user_id):
        raise BankError("frozen")
    bank = await session.scalar(select(Bank).where(Bank.id == bank_id).with_for_update())
    if bank is None:
        raise BankError("no_bank")
    if bank.owner_id == user_id:
        raise BankError("own_bank")
    if not bank.min_days <= days <= bank.max_days:
        raise BankError("bad_days")
    if amount > bank.capital:
        free = bank.capital  # до rollback: после него объект истёк
        await session.rollback()
        raise BankError("no_capital", free)
    has = await session.scalar(
        select(func.count(BankLoan.id)).where(BankLoan.borrower_id == user_id, BankLoan.bank_id == bank_id, BankLoan.status.in_(LOAN_OPEN))
    )
    if has:
        await session.rollback()
        raise BankError("has_loan")
    now = _now()
    bank.capital -= amount
    bank.lent_total += amount
    loan = BankLoan(
        bank_id=bank.id, lender_id=bank.owner_id, borrower_id=user_id, amount=amount, principal=amount, interest=0, paid=0,
        rate=bank.rate, days=days, status=LOAN_ACTIVE, taken_at=now, due_at=now + timedelta(days=days), accrued_days=0,
    )
    accrue(loan, now)  # первые сутки — сразу
    session.add(loan)
    with coin_reason(REASON_BANK):
        await grant(session, user_id, RES_NH, amount)
    await session.commit()
    return loan


async def repay(session: AsyncSession, redis: Redis, user_id: int, loan_id: int, amount: int | None) -> tuple[BankLoan, int, bool]:
    """Погасить часть (`amount`) или весь долг (`None`). Замороженный долг тоже гасится здесь — заморозка снимается."""
    await _lock(redis, user_id)
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id))
    if loan is None or loan.borrower_id != user_id or loan.status not in LOAN_OPEN:
        raise BankError("no_loan")
    if loan.bank_id is not None:  # порядок блокировок: банк → кредит → игрок
        await session.execute(select(Bank.id).where(Bank.id == loan.bank_id).with_for_update())
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id).with_for_update().execution_options(populate_existing=True))
    if loan.status not in LOAN_OPEN:
        await session.rollback()
        raise BankError("no_loan")
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
    to_interest, to_principal = _apply_payment(loan, pay)
    await _credit_lender(session, loan, to_interest + to_principal, to_interest)
    was_frozen = loan.status == LOAN_FROZEN
    closed = _close_if_paid(loan, now)
    await session.commit()
    if closed and was_frozen:
        await _refresh_frozen(session, redis, user_id)
    return loan, pay, closed and was_frozen


async def _refresh_frozen(session: AsyncSession, redis: Redis, user_id: int) -> None:
    """Флаг заморозки по факту: остался ли у игрока хоть один замороженный долг."""
    left = await session.scalar(select(func.count(BankLoan.id)).where(BankLoan.borrower_id == user_id, BankLoan.status == LOAN_FROZEN))
    if left:
        await redis.set(key_frozen(user_id), "1", ex=BANK_SWEEP_SECONDS * 3)
    else:
        await redis.delete(key_frozen(user_id))


# --- просрочки: конфискация, заморозка, удаление ------------------------------------------------

async def _take_coins(session: AsyncSession, user_id: int, need: int) -> int:
    coins = await session.scalar(select(User.nh_coins).where(User.id == user_id).with_for_update()) or 0
    take = min(max(0, coins), need)
    if take:
        with coin_reason(REASON_BANK):
            await spend(session, user_id, RES_NH, take)
    return take


async def _take_statists(session: AsyncSession, user_id: int, lender_id: int, need: int) -> int:
    """Статисты с самых слабых переходят владельцу банка (в тот же лагерь): боец засчитывается в долг по своей мощи ×
    цене мощи в магазине наёмников. Именно переходят, а не продаются — иначе через свой банк на твинке бесплатно
    навербованные статисты превращались бы в NHCoin."""
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
        "SELECT b.type, count(*) FROM businesses b JOIN districts d ON d.id = b.district_id "
        "WHERE d.owner_id = :u GROUP BY b.type"
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
    to_interest, to_principal = _apply_payment(loan, amount)
    if coins:
        await _credit_lender(session, loan, to_interest + to_principal, to_interest)


async def _delete_gang(session: AsyncSession, user_id: int) -> None:
    """Удаление банды за долг — как обычное удаление (потенциал, родословная, донат остаются)."""
    from bot.config.game import NH_COINS_STARTING, TICKET_STARTING
    from bot.db.repositories.gang import reset_player
    from bot.services.bloodline import apply_effects as apply_bloodline_effects
    from bot.services.donate import apply_all as apply_donate

    await reset_player(session, user_id, nh_coins=NH_COINS_STARTING, tickets=TICKET_STARTING)
    await apply_bloodline_effects(session, user_id)
    await apply_donate(session, user_id)


async def _process(session: AsyncSession, loan_id: int, now: datetime) -> list[Notice]:
    """Один просроченный или замороженный кредит — в своей транзакции. → пуши."""
    loan = await session.scalar(select(BankLoan).where(BankLoan.id == loan_id))
    if loan is None or loan.status not in LOAN_OPEN:
        return []
    if loan.bank_id is not None:
        await session.execute(select(Bank.id).where(Bank.id == loan.bank_id).with_for_update())
    loan = await session.scalar(
        select(BankLoan).where(BankLoan.id == loan_id).with_for_update(skip_locked=True).execution_options(populate_existing=True)
    )
    if loan is None or loan.status not in LOAN_OPEN:
        await session.rollback()
        return []
    notices: list[Notice] = []
    who = loan.borrower_id
    if loan.status == LOAN_ACTIVE:
        if loan.due_at > now:
            await session.rollback()
            return []
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
    else:  # заморожен: весь доход — в долг
        from bot.services.business import accrue as accrue_income

        await accrue_income(session, who)
        coins = await _take_coins(session, who, loan.debt)
        await _collect(session, loan, coins)
        if _close_if_paid(loan, now):
            notices += [Notice(who, "unfrozen", {}), Notice(loan.lender_id, "lender_repaid", {"amount": loan.paid})]
        elif loan.frozen_until is not None and loan.frozen_until <= now:
            left = loan.debt
            loan.status = LOAN_DEFAULTED
            loan.closed_at = now
            # Банды больше нет — остальные её кредиты тоже списаны (иначе новую банду удаляли бы снова).
            await session.execute(
                update(BankLoan).where(BankLoan.borrower_id == who, BankLoan.status.in_(LOAN_OPEN), BankLoan.id != loan.id)
                .values(status=LOAN_DEFAULTED, closed_at=now)
            )
            await _delete_gang(session, who)
            notices += [Notice(who, "deleted", {"left": left}), Notice(loan.lender_id, "lender_deleted", {"left": left})]
    await session.commit()
    return notices


async def sweep(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> list[Notice]:
    """Фоновый проход (`main.py`): просроченные → конфискация/заморозка, замороженные → доход в долг/удаление.
    Флаги заморозки в Redis выставляются заново каждый проход (самовосстановление после сброса Redis)."""
    now = _now()
    async with session_factory() as session:
        ids = list((await session.scalars(
            select(BankLoan.id).where(
                ((BankLoan.status == LOAN_ACTIVE) & (BankLoan.due_at <= now)) | (BankLoan.status == LOAN_FROZEN)
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
        if n.code in ("unfrozen", "deleted") and n.user_id not in frozen:
            await redis.delete(key_frozen(n.user_id))
    return notices

