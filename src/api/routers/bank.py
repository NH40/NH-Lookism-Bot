"""Банки игроков и кредиты в Mini App — те же операции, что «💳 Кредиты» в боте (`services/bank`)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, require_user
from bot.config.bank import BANK_DAYS_MAX, BANK_DAYS_MIN, BANK_FREEZE_DAYS, BANK_MIN_CAPITAL, BANK_MIN_LOAN, BANK_RATE_MAX, BANK_RATE_MIN
from bot.constant.bank import LOAN_FROZEN
from bot.db.models.gang import Gang
from bot.db.models.user import User
from bot.handlers.bank.bank import _error, rate_label
from bot.services import bank as bank_svc
from bot.texts.bank import CREATED, DEPOSITED, REPAID_FULL, REPAID_PART, REPAID_UNFROZEN, TAKEN, TERMS_SET, WITHDRAWN, CLOSED

router = APIRouter(prefix="/api/bank", tags=["bank"])


class BankOut(BaseModel):
    id: int
    owner: str
    capital: int
    rate: float
    rate_label: str
    min_days: int
    max_days: int
    open_loans: int
    lent_total: int


class LoanOut(BaseModel):
    id: int
    name: str  # банк (для заёмщика) или должник (для владельца)
    amount: int
    debt: int
    principal: int
    interest: int
    paid: int
    rate_label: str
    days: int
    frozen: bool
    due_in: int  # секунд до срока (0 — срок вышел)
    frozen_in: int  # секунд до удаления банды (заморожен)


class MyBankOut(BaseModel):
    capital: int
    lent: int
    open_loans: int
    rate: float
    rate_label: str
    min_days: int
    max_days: int
    earned: int
    loans: list[LoanOut]


class BankHomeOut(BaseModel):
    banks: list[BankOut]
    more: bool
    page: int
    loans: list[LoanOut]
    my_bank: MyBankOut | None
    coins: int
    frozen: bool
    limits: dict


class MessageOut(BaseModel):
    message: str


def _secs(moment: datetime | None) -> int:
    return max(0, int((moment - datetime.now(timezone.utc)).total_seconds())) if moment else 0


async def _names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict((await session.execute(select(Gang.user_id, Gang.name).where(Gang.user_id.in_(ids)))).all())


def _loan(loan, name: str) -> LoanOut:
    return LoanOut(
        id=loan.id, name=name, amount=loan.amount, debt=loan.debt, principal=loan.principal, interest=loan.interest, paid=loan.paid,
        rate_label=rate_label(loan.rate), days=loan.days, frozen=loan.status == LOAN_FROZEN, due_in=_secs(loan.due_at),
        frozen_in=_secs(loan.frozen_until) if loan.status == LOAN_FROZEN else 0,
    )


def _bank(r) -> BankOut:
    return BankOut(id=r.id, owner=r.owner_name, capital=r.capital, rate=r.rate, rate_label=rate_label(r.rate), min_days=r.min_days,
                   max_days=r.max_days, open_loans=r.open_loans, lent_total=r.lent_total)


@router.get("", response_model=BankHomeOut)
async def home(page: int = 0, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> BankHomeOut:
    await require_user(session, user_id, need_city=False)
    rows, more = await bank_svc.list_banks(session, user_id, max(0, page))
    loans = await bank_svc.my_loans(session, user_id)
    lender_names = await _names(session, {loan.lender_id for loan in loans})
    my = None
    bank = await bank_svc.get_bank(session, user_id)
    if bank is not None:
        lent, n = await bank_svc.lent_out(session, bank.id)
        issued = await bank_svc.issued_loans(session, user_id)
        debtor_names = await _names(session, {loan.borrower_id for loan in issued})
        my = MyBankOut(capital=bank.capital, lent=lent, open_loans=n, rate=bank.rate, rate_label=rate_label(bank.rate), min_days=bank.min_days,
                       max_days=bank.max_days, earned=bank.earned_total, loans=[_loan(x, debtor_names.get(x.borrower_id, "—")) for x in issued])
    coins = int(await session.scalar(select(User.nh_coins).where(User.id == user_id)) or 0)
    return BankHomeOut(
        banks=[_bank(r) for r in rows], more=more, page=page, loans=[_loan(x, lender_names.get(x.lender_id, "—")) for x in loans],
        my_bank=my, coins=coins, frozen=await bank_svc.is_frozen(redis, user_id),
        limits={"rate_min": BANK_RATE_MIN, "rate_max": BANK_RATE_MAX, "days_min": BANK_DAYS_MIN, "days_max": BANK_DAYS_MAX,
                "min_capital": BANK_MIN_CAPITAL, "min_loan": BANK_MIN_LOAN, "freeze_days": BANK_FREEZE_DAYS},
    )


class TakeIn(BaseModel):
    bank_id: int
    amount: int
    days: int


class RepayIn(BaseModel):
    loan_id: int
    amount: int | None = None  # None — всё


class TermsIn(BaseModel):
    rate_percent: float
    min_days: int
    max_days: int


class CreateIn(TermsIn):
    capital: int


class AmountIn(BaseModel):
    amount: int


async def _do(coro):
    try:
        return await coro
    except bank_svc.BankError as exc:
        raise bad(clean_label(_error(exc)))


def _n(x: int) -> str:
    return f"{x:,}".replace(",", " ")


@router.post("/take", response_model=MessageOut)
async def take(body: TakeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> MessageOut:
    await require_user(session, user_id, need_city=False)
    loan = await _do(bank_svc.take_loan(session, redis, user_id, body.bank_id, body.amount, body.days))
    due = (loan.due_at.astimezone(timezone.utc)).strftime("%d.%m %H:%M UTC")
    return MessageOut(message=clean_label(TAKEN.format(amount=_n(loan.amount), due=due, debt=_n(loan.debt))))


@router.post("/repay", response_model=MessageOut)
async def repay(body: RepayIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    loan, paid, unfrozen = await _do(bank_svc.repay(session, redis, user_id, body.loan_id, body.amount))
    if unfrozen:
        return MessageOut(message=clean_label(REPAID_UNFROZEN))
    if loan.debt == 0:
        return MessageOut(message=clean_label(REPAID_FULL.format(id=loan.id)))
    return MessageOut(message=clean_label(REPAID_PART.format(paid=_n(paid), debt=_n(loan.debt))))


@router.post("/create", response_model=MessageOut)
async def create(body: CreateIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                 redis: Redis = Depends(get_redis)) -> MessageOut:
    await require_user(session, user_id, need_city=False)
    b = await _do(bank_svc.create_bank(session, redis, user_id, body.capital, body.rate_percent / 100, body.min_days, body.max_days))
    return MessageOut(message=clean_label(CREATED.format(capital=_n(b.capital), rate=rate_label(b.rate), min=b.min_days, max=b.max_days)))


@router.post("/terms", response_model=MessageOut)
async def terms(body: TermsIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    await _do(bank_svc.set_terms(session, redis, user_id, body.rate_percent / 100, body.min_days, body.max_days))
    return MessageOut(message=clean_label(TERMS_SET))


@router.post("/deposit", response_model=MessageOut)
async def deposit(body: AmountIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> MessageOut:
    capital = await _do(bank_svc.add_capital(session, redis, user_id, body.amount))
    return MessageOut(message=clean_label(DEPOSITED.format(capital=_n(capital))))


@router.post("/withdraw", response_model=MessageOut)
async def withdraw(body: AmountIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                   redis: Redis = Depends(get_redis)) -> MessageOut:
    capital = await _do(bank_svc.withdraw(session, redis, user_id, body.amount))
    return MessageOut(message=clean_label(WITHDRAWN.format(capital=_n(capital))))


@router.post("/close", response_model=MessageOut)
async def close(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    capital = await _do(bank_svc.close_bank(session, redis, user_id))
    return MessageOut(message=clean_label(CLOSED.format(capital=_n(capital))))
