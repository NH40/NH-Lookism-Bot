"""Банки игроков и кредиты в Mini App — те же операции, что «💳 Кредиты» в боте (`services/bank`, банки v2):
заявка → одобрение банком → договор → подпись; участники банка; пуши — тем же `send_pushes`, что в боте."""
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
from api.routers._common import bad, clean_label, require_user, telegram_bot
from bot.config.bank import (
    BANK_DAYS_MAX,
    BANK_DAYS_MIN,
    BANK_FIXED_MAX,
    BANK_FIXED_MIN,
    BANK_FREEZE_DAYS,
    BANK_HOURLY_MAX,
    BANK_HOURLY_MIN,
    BANK_MEMBERS_MAX,
    BANK_MIN_CAPITAL,
    BANK_MIN_LOAN,
    BANK_PENALTY_MAX,
    BANK_SLAVE_SHARE,
)
from bot.constant import bank as C
from bot.db.models.gang import Gang
from bot.db.models.user import User
from bot.handlers.bank.bank import error_text, send_pushes
from bot.services import bank as svc
from bot.texts.bank import bank as t

router = APIRouter(prefix="/api/bank", tags=["bank"])


class BankOut(BaseModel):
    id: int
    owner: str
    capital: int
    fixed_rate: float | None
    hourly_rate: float | None
    penalty_rate: float
    min_days: int
    max_days: int
    open_loans: int


class LoanOut(BaseModel):
    id: int
    name: str  # банк (для заёмщика) или заёмщик (для банка)
    status: str
    kind: str
    rate: float
    penalty_rate: float
    amount: int
    debt: int
    principal: int
    interest: int
    penalty: int
    paid: int
    days: int
    terms: str | None
    due_in: int
    frozen_in: int
    offer_in: int


class MemberOut(BaseModel):
    id: int
    name: str


class TeamOut(BaseModel):
    is_owner: bool
    owner: str
    capital: int
    lent: int
    reserved: int
    open_loans: int
    fixed_rate: float | None
    hourly_rate: float | None
    penalty_rate: float
    min_days: int
    max_days: int
    earned: int
    members: list[MemberOut]
    apps: list[LoanOut]
    loans: list[LoanOut]


class BankHomeOut(BaseModel):
    banks: list[BankOut]
    more: bool
    page: int
    loans: list[LoanOut]
    team: TeamOut | None
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


def _loan(x, name: str) -> LoanOut:
    return LoanOut(
        id=x.id, name=name, status=x.status, kind=x.kind, rate=x.rate, penalty_rate=x.penalty_rate or 0.0, amount=x.amount, debt=x.debt,
        principal=x.principal, interest=x.interest, penalty=x.penalty, paid=x.paid, days=x.days, terms=x.terms,
        due_in=_secs(x.due_at) if x.status in C.LOAN_OPEN else 0, frozen_in=_secs(x.frozen_until) if x.status == C.LOAN_FROZEN else 0,
        offer_in=_secs(x.offer_until) if x.status == C.LOAN_OFFERED else 0,
    )


@router.get("", response_model=BankHomeOut)
async def home(page: int = 0, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> BankHomeOut:
    await require_user(session, user_id, need_city=False)
    rows, more = await svc.list_banks(session, user_id, max(0, page))
    loans = await svc.my_loans(session, user_id)
    team_out = None
    team = await svc.team_of(session, user_id)
    team_loans = await svc.team_loans(session, team.bank.id) if team else []
    names = await _names(session, {x.lender_id for x in loans} | {x.borrower_id for x in team_loans} | ({team.bank.owner_id, *team.members} if team else set()))
    if team is not None:
        b = team.bank
        lent, n, reserved = await svc.lent_out(session, b.id)
        team_out = TeamOut(
            is_owner=team.is_owner, owner=names.get(b.owner_id, "—"), capital=b.capital, lent=lent, reserved=reserved, open_loans=n,
            fixed_rate=b.fixed_rate, hourly_rate=b.hourly_rate, penalty_rate=b.penalty_rate or 0.0, min_days=b.min_days, max_days=b.max_days,
            earned=b.earned_total, members=[MemberOut(id=m, name=names.get(m, "—")) for m in team.members],
            apps=[_loan(x, names.get(x.borrower_id, "—")) for x in team_loans if x.status == C.LOAN_PENDING],
            loans=[_loan(x, names.get(x.borrower_id, "—")) for x in team_loans if x.status in C.LOAN_OPEN],
        )
    coins = int(await session.scalar(select(User.nh_coins).where(User.id == user_id)) or 0)
    return BankHomeOut(
        banks=[BankOut(id=r.id, owner=r.owner_name, capital=r.capital, fixed_rate=r.fixed_rate, hourly_rate=r.hourly_rate, penalty_rate=r.penalty_rate,
                       min_days=r.min_days, max_days=r.max_days, open_loans=r.open_loans) for r in rows],
        more=more, page=page, loans=[_loan(x, names.get(x.lender_id, "—")) for x in loans], team=team_out, coins=coins,
        frozen=await svc.is_frozen(redis, user_id),
        limits={"fixed_min": BANK_FIXED_MIN, "fixed_max": BANK_FIXED_MAX, "hourly_min": BANK_HOURLY_MIN, "hourly_max": BANK_HOURLY_MAX,
                "penalty_max": BANK_PENALTY_MAX, "days_min": BANK_DAYS_MIN, "days_max": BANK_DAYS_MAX, "min_capital": BANK_MIN_CAPITAL,
                "min_loan": BANK_MIN_LOAN, "freeze_days": BANK_FREEZE_DAYS, "slave_share": round(BANK_SLAVE_SHARE * 100), "members_max": BANK_MEMBERS_MAX},
    )


async def _do(coro):
    try:
        return await coro
    except svc.BankError as exc:
        raise bad(clean_label(error_text(exc)))


async def _push(session: AsyncSession, notices) -> None:
    if notices:
        async with telegram_bot() as bot:
            await send_pushes(bot, session, notices)


def _n(x: int) -> str:
    return f"{x:,}".replace(",", " ")


class ApplyIn(BaseModel):
    bank_id: int
    kind: str
    amount: int
    days: int


class LoanIn(BaseModel):
    loan_id: int


class RepayIn(LoanIn):
    amount: int | None = None


class ApproveIn(LoanIn):
    terms: str | None = None


class TermsIn(BaseModel):
    fixed_percent: float | None = None
    hourly_percent: float | None = None
    penalty_percent: float = 0.0
    min_days: int
    max_days: int

    def args(self) -> tuple:
        return (None if self.fixed_percent is None else self.fixed_percent / 100, None if self.hourly_percent is None else self.hourly_percent / 100,
                (self.penalty_percent or 0.0) / 100, self.min_days, self.max_days)


class CreateIn(TermsIn):
    capital: int


class AmountIn(BaseModel):
    amount: int


class MemberIn(BaseModel):
    username: str


class MemberIdIn(BaseModel):
    user_id: int



@router.post("/apply", response_model=MessageOut)
async def apply(body: ApplyIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    await require_user(session, user_id, need_city=False)
    _, notices = await _do(svc.apply_loan(session, redis, user_id, body.bank_id, body.kind, body.amount, body.days))
    await _push(session, notices)
    return MessageOut(message=clean_label(t.APPLIED))


@router.post("/cancel", response_model=MessageOut)
async def cancel(body: LoanIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                 redis: Redis = Depends(get_redis)) -> MessageOut:
    await _do(svc.cancel(session, redis, user_id, body.loan_id))
    return MessageOut(message=clean_label(t.CANCELLED))


@router.post("/sign", response_model=MessageOut)
async def sign(body: LoanIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> MessageOut:
    loan, notices = await _do(svc.sign(session, redis, user_id, body.loan_id))
    await _push(session, notices)
    return MessageOut(message=f"Договор подписан: +{_n(loan.amount)} NHCoin. Долг {_n(loan.debt)}.")


@router.post("/decline", response_model=MessageOut)
async def decline(body: LoanIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> MessageOut:
    notices = await _do(svc.decline(session, redis, user_id, body.loan_id))
    await _push(session, notices)
    return MessageOut(message=clean_label(t.DECLINED))


@router.post("/repay", response_model=MessageOut)
async def repay(body: RepayIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    loan, paid, unfrozen = await _do(svc.repay(session, redis, user_id, body.loan_id, body.amount))
    if unfrozen:
        return MessageOut(message=clean_label(t.REPAID_UNFROZEN))
    if loan.debt == 0:
        return MessageOut(message=clean_label(t.REPAID_FULL.format(id=loan.id)))
    return MessageOut(message=clean_label(t.REPAID_PART.format(paid=_n(paid), debt=_n(loan.debt))))


@router.post("/approve", response_model=MessageOut)
async def approve(body: ApproveIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> MessageOut:
    loan, notices = await _do(svc.approve(session, redis, user_id, body.loan_id, body.terms))
    await _push(session, notices)
    return MessageOut(message=clean_label(t.APPROVED.format(id=loan.id)))


@router.post("/reject", response_model=MessageOut)
async def reject(body: LoanIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                 redis: Redis = Depends(get_redis)) -> MessageOut:
    notices = await _do(svc.reject(session, redis, user_id, body.loan_id))
    await _push(session, notices)
    return MessageOut(message=clean_label(t.REJECTED.format(id=body.loan_id)))


@router.post("/create", response_model=MessageOut)
async def create(body: CreateIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                 redis: Redis = Depends(get_redis)) -> MessageOut:
    await require_user(session, user_id, need_city=False)
    b = await _do(svc.create_bank(session, redis, user_id, body.capital, *body.args()))
    return MessageOut(message=clean_label(t.CREATED.format(capital=_n(b.capital))))


@router.post("/terms", response_model=MessageOut)
async def terms(body: TermsIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    await _do(svc.set_terms(session, redis, user_id, *body.args()))
    return MessageOut(message=clean_label(t.TERMS_SET))


@router.post("/deposit", response_model=MessageOut)
async def deposit(body: AmountIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> MessageOut:
    capital = await _do(svc.add_capital(session, redis, user_id, body.amount))
    return MessageOut(message=clean_label(t.DEPOSITED.format(capital=_n(capital))))


@router.post("/withdraw", response_model=MessageOut)
async def withdraw(body: AmountIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                   redis: Redis = Depends(get_redis)) -> MessageOut:
    capital = await _do(svc.withdraw(session, redis, user_id, body.amount))
    return MessageOut(message=clean_label(t.WITHDRAWN.format(capital=_n(capital))))


@router.post("/close", response_model=MessageOut)
async def close(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                redis: Redis = Depends(get_redis)) -> MessageOut:
    capital = await _do(svc.close_bank(session, redis, user_id))
    return MessageOut(message=clean_label(t.CLOSED.format(capital=_n(capital))))


@router.post("/members/add", response_model=MessageOut)
async def member_add(body: MemberIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> MessageOut:
    _, name = await _do(svc.add_member(session, redis, user_id, body.username))
    return MessageOut(message=clean_label(t.MEMBER_ADDED.format(name=name)))


@router.post("/members/remove", response_model=MessageOut)
async def member_remove(body: MemberIdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                        redis: Redis = Depends(get_redis)) -> MessageOut:
    await _do(svc.remove_member(session, redis, user_id, body.user_id))
    return MessageOut(message="Участник убран из банка.")


@router.post("/leave", response_model=MessageOut)
async def leave(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> MessageOut:
    await svc.leave_bank(session, user_id)
    return MessageOut(message="Ты вышел из банка.")

