"""Банки игроков и кредиты (хендлеры). Банки v2 — 2026-11-14: заявка → одобрение банком → договор → подпись.
Вход — «💳 Кредиты» в магазине. `send_pushes()` — пуши (заявки банкирам с кнопками, договоры заёмщикам, просрочки),
им пользуются и хендлеры, и фоновый проход (`main.py`), и API Mini App."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from bot.db.models.bank import BankLoan
from bot.db.models.gang import Gang
from bot.db.models.user import User
from bot.keyboards import bank as kb
from bot.services import bank as svc
from bot.services.gang import get_gang
from bot.states.bank import BankStates
from bot.texts.bank import bank as t
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_countdown, format_number

log = logging.getLogger(__name__)
router = Router(name="bank")
SHARE = round(BANK_SLAVE_SHARE * 100)


# --- форматирование ----------------------------------------------------------------------------

def pct(rate: float | None) -> str:
    if rate is None:
        return "—"
    return f"{rate * 100:.2f}".rstrip("0").rstrip(".") + "%"


rate_label = pct


def short(n: int) -> str:
    for size, suffix in ((10**12, "трлн"), (10**9, "млрд"), (10**6, "млн"), (10**3, "тыс")):
        if n >= size:
            return f"{n / size:.1f}".rstrip("0").rstrip(".") + " " + suffix
    return str(n)


def date_label(moment: datetime) -> str:
    return (moment + timedelta(hours=3)).strftime("%d.%m %H:%M") + " МСК"


def left_label(moment: datetime | None) -> str:
    return format_countdown(max(0, int((moment - datetime.now(timezone.utc)).total_seconds()))) if moment else "—"


def kinds_short(fixed: float | None, hourly: float | None) -> str:
    parts = []
    if fixed is not None:
        parts.append(f"фикс +{pct(fixed)}")
    if hourly is not None:
        parts.append(f"{pct(hourly)}/ч")
    return " · ".join(parts) or "—"


def bank_kinds(fixed: float | None, hourly: float | None) -> list[str]:
    return [k for k, r in ((C.KIND_FIXED, fixed), (C.KIND_HOURLY, hourly)) if r is not None]


def loan_cost(kind: str, rate: float, amount: int, days: int) -> str:
    if kind == C.KIND_FIXED:
        return t.COST_FIXED.format(total=format_number(amount + max(1, round(amount * rate))), rate=pct(rate))
    per_hour = max(1, round(amount * rate))
    return t.COST_HOURLY.format(per_hour=format_number(per_hour), total=format_number(amount + per_hour * days * 24))


def contract_text(loan: BankLoan, bank_name: str, borrower: str = "—") -> str:
    """Договор по шаблону пользователя: банк, владелец, заёмщик, сумма, ставка своего вида, срок, просрочка, рабство."""
    fixed = loan.kind == C.KIND_FIXED
    rate_line = (t.CONTRACT_RATE_FIXED.format(rate=pct(loan.rate), total=format_number(loan.amount + max(1, round(loan.amount * loan.rate))))
                 if fixed else t.CONTRACT_RATE_HOURLY.format(rate=pct(loan.rate)))
    return t.CONTRACT.format(
        id=loan.id, kind_title=t.CONTRACT_KIND_TITLE.get(loan.kind, loan.kind), bank=f"банк {esc(bank_name)}", owner=esc(bank_name),
        borrower=esc(borrower), amount=format_number(loan.amount), rate_line=rate_line, days=loan.days,
        interest_text=t.CONTRACT_INTEREST_FIXED if fixed else t.CONTRACT_INTEREST_HOURLY,
        repay_line="" if fixed else t.CONTRACT_REPAY_HOURLY, freeze=BANK_FREEZE_DAYS,
        penalty=f"{pct(loan.penalty_rate)} в час на долг" if loan.penalty_rate else "нет", share=SHARE,
        terms=t.CONTRACT_TERMS.format(terms=esc(loan.terms)) if loan.terms else "",
        until=date_label(loan.offer_until) if loan.offer_until else "—",
    )


def error_text(exc: svc.BankError) -> str:
    value = exc.value if isinstance(exc.value, float) else format_number(int(exc.value))
    return t.ERRORS.get(exc.code, exc.code).format(value=value)


_error = error_text


def _number(text: str | None) -> int | None:
    raw = (text or "").replace(" ", "").replace(",", "").replace("_", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def parse_terms(text: str | None) -> tuple[float | None, float | None, float, int, int] | None:
    """«20 0.5 1 3 14» → (0.20, 0.005, 0.01, 3, 14); прочерк — вид выключен (у пени — 0)."""
    parts = (text or "").replace(",", ".").replace("%", " ").split()
    if len(parts) != 5:
        return None
    off = ("-", "—", "нет")
    try:
        fixed = None if parts[0] in off else float(parts[0]) / 100
        hourly = None if parts[1] in off else float(parts[1]) / 100
        penalty = 0.0 if parts[2] in off else float(parts[2]) / 100
        return fixed, hourly, penalty, int(parts[3]), int(parts[4])
    except ValueError:
        return None


async def _names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = await session.execute(select(Gang.user_id, Gang.name).where(Gang.user_id.in_(ids)))
    return {uid: esc(name) for uid, name in rows.all()}


async def _coins(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(User.nh_coins).where(User.id == user_id)) or 0)


async def _edit(callback: CallbackQuery, text: str, markup) -> None:
    from bot.utils.safe_edit import safe_edit_text

    await safe_edit_text(callback.message, text, reply_markup=markup)


# --- список и карточка банка, заявка ------------------------------------------------------------

async def _show_list(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    rows, more = await svc.list_banks(session, callback.from_user.id, page)
    buttons = [(t.BANK_ROW_BTN.format(name=r.owner_name[:14], kinds=kinds_short(r.fixed_rate, r.hourly_rate), min=r.min_days, max=r.max_days,
                                      capital=short(r.capital)), r.id) for r in rows]
    text = t.LIST_SCREEN.format(freeze=BANK_FREEZE_DAYS, share=SHARE, body=t.LIST_HINT if rows else t.LIST_EMPTY)
    await _edit(callback, text, kb.list_menu(buttons, page, more))


@router.callback_query(F.data == C.CB_BANK_OPEN)
async def cb_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await _show_list(callback, session, 0)


@router.callback_query(F.data.startswith(C.CB_BANK_PAGE_PREFIX))
async def cb_page(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(C.CB_BANK_PAGE_PREFIX)
    await callback.answer()
    await _show_list(callback, session, int(raw) if raw.isdigit() else 0)


@router.callback_query(F.data.startswith(C.CB_BANK_VIEW_PREFIX))
async def cb_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    raw = callback.data.removeprefix(C.CB_BANK_VIEW_PREFIX)
    card = await svc.bank_card(session, int(raw)) if raw.isdigit() else None
    if card is None:
        await callback.answer(t.ERRORS["no_bank"], show_alert=True)
        return
    await callback.answer()
    kinds = ((t.CARD_KIND_FIXED.format(rate=pct(card.fixed_rate)) if card.fixed_rate is not None else "")
             + (t.CARD_KIND_HOURLY.format(rate=pct(card.hourly_rate)) if card.hourly_rate is not None else ""))
    text = t.CARD.format(name=esc(card.owner_name), kinds=kinds, min=card.min_days, max=card.max_days,
                         penalty=f"{pct(card.penalty_rate)} в час" if card.penalty_rate else "нет", capital=format_number(card.capital), open=card.open_loans)
    can = card.owner_id != callback.from_user.id and card.capital >= BANK_MIN_LOAN
    await _edit(callback, text, kb.card_menu(card.id, bank_kinds(card.fixed_rate, card.hourly_rate) if can else []))


@router.callback_query(F.data.startswith(C.CB_BANK_TAKE_PREFIX))
async def cb_take(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw_id, _, kind = callback.data.removeprefix(C.CB_BANK_TAKE_PREFIX).partition(":")
    card = await svc.bank_card(session, int(raw_id)) if raw_id.isdigit() else None
    if card is None or kind not in bank_kinds(card.fixed_rate, card.hourly_rate):
        await callback.answer(t.ERRORS["no_bank"], show_alert=True)
        return
    await callback.answer()
    await state.set_state(BankStates.take_amount)
    await state.update_data(bank_id=card.id, kind=kind)
    await _edit(callback, t.ASK_AMOUNT.format(kind=t.KIND_NAMES[kind], min=format_number(BANK_MIN_LOAN), max=format_number(card.capital)),
                kb.back_menu(f"{C.CB_BANK_VIEW_PREFIX}{card.id}"))


@router.message(BankStates.take_amount)
async def on_take_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    amount = _number(message.text)
    data = await state.get_data()
    card = await svc.bank_card(session, data.get("bank_id", 0))
    if card is None:
        await state.clear()
        await message.answer(t.ERRORS["no_bank"])
        return
    if amount is None:
        await message.answer(t.BAD_NUMBER)
        return
    if amount > card.capital or amount < BANK_MIN_LOAN:
        await message.answer(t.ERRORS["no_capital"].format(value=format_number(card.capital)) if amount > card.capital
                             else t.ERRORS["min_loan"].format(value=format_number(BANK_MIN_LOAN)))
        return
    await state.update_data(amount=amount)
    await state.set_state(None)
    await message.answer(t.ASK_DAYS.format(amount=format_number(amount)), reply_markup=kb.days_menu(card.min_days, card.max_days, card.id))


@router.callback_query(F.data.startswith(C.CB_BANK_DAYS_PREFIX))
async def cb_days(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    raw = callback.data.removeprefix(C.CB_BANK_DAYS_PREFIX)
    card = await svc.bank_card(session, data.get("bank_id", 0))
    if card is None or not data.get("amount") or not raw.isdigit():
        await callback.answer(t.ERRORS["no_bank"], show_alert=True)
        return
    kind = data.get("kind", C.KIND_FIXED)
    rate = card.fixed_rate if kind == C.KIND_FIXED else card.hourly_rate
    days, amount = int(raw), int(data["amount"])
    await state.update_data(days=days)
    await callback.answer()
    text = t.CONFIRM.format(name=esc(card.owner_name), amount=format_number(amount), days=days, kind=t.KIND_NAMES[kind],
                            cost=loan_cost(kind, rate or 0.0, amount, days))
    await _edit(callback, text, kb.confirm_menu(card.id))


@router.callback_query(F.data == C.CB_BANK_CONFIRM)
async def cb_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    data = await state.get_data()
    if not all(data.get(k) for k in ("bank_id", "amount", "days", "kind")):
        await callback.answer(t.ERRORS["no_bank"], show_alert=True)
        return
    try:
        _, notices = await svc.apply_loan(session, redis, callback.from_user.id, int(data["bank_id"]), data["kind"], int(data["amount"]), int(data["days"]))
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await _edit(callback, t.APPLIED, kb.back_menu(C.CB_BANK_LOANS))
    await send_pushes(callback.bot, session, notices)


# --- мои кредиты и заявки ----------------------------------------------------------------------

async def render_loans(session: AsyncSession, user_id: int) -> tuple[str, list[int], list[int], list[int]]:
    loans = await svc.my_loans(session, user_id)
    names = await _names(session, {loan.lender_id for loan in loans})
    rows, opened, pending, offered = [], [], [], []
    for loan in loans:
        name = names.get(loan.lender_id, "—")
        kind = t.KIND_NAMES.get(loan.kind, loan.kind)
        if loan.status in C.LOAN_WAITING:
            state = t.APP_PENDING if loan.status == C.LOAN_PENDING else t.APP_OFFERED
            rows.append(t.APP_ROW.format(id=loan.id, name=name, amount=format_number(loan.amount), days=loan.days, kind=kind, state=state))
            (pending if loan.status == C.LOAN_PENDING else offered).append(loan.id)
            continue
        if loan.status == C.LOAN_FROZEN:
            when = t.LOAN_FROZEN.format(until=date_label(loan.frozen_until), left=left_label(loan.frozen_until))
        elif loan.status == C.LOAN_SLAVE:
            when = t.LOAN_SLAVE.format(share=SHARE)
        else:
            when = t.LOAN_DUE.format(due=date_label(loan.due_at), left=left_label(loan.due_at))
        rows.append(t.LOAN_ROW.format(id=loan.id, name=name, kind=kind, debt=format_number(loan.debt), principal=format_number(loan.principal),
                                      interest=format_number(loan.interest), penalty=t.LOAN_PENALTY.format(p=format_number(loan.penalty)) if loan.penalty else "",
                                      when=when))
        opened.append(loan.id)
    return t.LOANS_SCREEN.format(body="\n".join(rows) if rows else t.LOANS_EMPTY), opened, pending, offered


async def _show_loans(callback: CallbackQuery, session: AsyncSession) -> None:
    text, opened, pending, offered = await render_loans(session, callback.from_user.id)
    await _edit(callback, text, kb.loans_menu(opened, pending, offered))


@router.callback_query(F.data == C.CB_BANK_LOANS)
async def cb_loans(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    await _show_loans(callback, session)


async def _repay(session: AsyncSession, redis: Redis, user_id: int, loan_id: int, amount: int | None) -> str:
    try:
        loan, paid, unfrozen = await svc.repay(session, redis, user_id, loan_id, amount)
    except svc.BankError as exc:
        return error_text(exc)
    if unfrozen:
        return t.REPAID_UNFROZEN
    if loan.debt == 0:
        return t.REPAID_FULL.format(id=loan.id)
    return t.REPAID_PART.format(paid=format_number(paid), debt=format_number(loan.debt))


@router.callback_query(F.data.startswith(C.CB_BANK_REPAY_ALL_PREFIX))
async def cb_repay_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(C.CB_BANK_REPAY_ALL_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    await callback.answer(await _repay(session, redis, callback.from_user.id, int(raw), None), show_alert=True)
    await _show_loans(callback, session)


@router.callback_query(F.data.startswith(C.CB_BANK_REPAY_PREFIX))
async def cb_repay(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(C.CB_BANK_REPAY_PREFIX)
    loans = {loan.id: loan for loan in await svc.my_loans(session, callback.from_user.id) if loan.status in C.LOAN_OPEN}
    loan = loans.get(int(raw)) if raw.isdigit() else None
    if loan is None:
        await callback.answer(t.ERRORS["no_loan"], show_alert=True)
        return
    await callback.answer()
    await state.set_state(BankStates.repay_amount)
    await state.update_data(loan_id=loan.id)
    await _edit(callback, t.ASK_REPAY.format(id=loan.id, debt=format_number(loan.debt), coins=format_number(await _coins(session, callback.from_user.id))),
                kb.back_menu(C.CB_BANK_LOANS))


@router.message(BankStates.repay_amount)
async def on_repay_amount(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    if amount is None:
        await message.answer(t.BAD_NUMBER)
        return
    loan_id = int((await state.get_data()).get("loan_id", 0))
    await state.clear()
    await message.answer(await _repay(session, redis, message.from_user.id, loan_id, amount))
    text, opened, pending, offered = await render_loans(session, message.from_user.id)
    await message.answer(text, reply_markup=kb.loans_menu(opened, pending, offered))


def _id(data: str, prefix: str) -> int:
    raw = data.removeprefix(prefix)
    return int(raw) if raw.isdigit() else 0


@router.callback_query(F.data.startswith(C.CB_BANK_CANCEL_PREFIX))
async def cb_cancel(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        await svc.cancel(session, redis, callback.from_user.id, _id(callback.data, C.CB_BANK_CANCEL_PREFIX))
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(t.CANCELLED)
    await _show_loans(callback, session)


@router.callback_query(F.data.startswith(C.CB_BANK_SIGN_PREFIX))
async def cb_sign(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        loan, notices = await svc.sign(session, redis, callback.from_user.id, _id(callback.data, C.CB_BANK_SIGN_PREFIX))
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await _edit(callback, t.SIGNED.format(amount=format_number(loan.amount), due=date_label(loan.due_at), debt=format_number(loan.debt)),
                kb.back_menu(C.CB_BANK_LOANS))
    await send_pushes(callback.bot, session, notices)


@router.callback_query(F.data.startswith(C.CB_BANK_DECLINE_PREFIX))
async def cb_decline(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        notices = await svc.decline(session, redis, callback.from_user.id, _id(callback.data, C.CB_BANK_DECLINE_PREFIX))
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await _edit(callback, t.DECLINED, kb.back_menu(C.CB_BANK_LOANS))
    await send_pushes(callback.bot, session, notices)


# --- заявки в мой банк (владелец и участники) ---------------------------------------------------

@router.callback_query(F.data.startswith(C.CB_BANK_APPROVE_TERMS_PREFIX))
async def cb_approve_terms(callback: CallbackQuery, state: FSMContext) -> None:
    loan_id = _id(callback.data, C.CB_BANK_APPROVE_TERMS_PREFIX)
    await callback.answer()
    await state.set_state(BankStates.approve_terms)
    await state.update_data(loan_id=loan_id)
    await callback.message.answer(t.ASK_APPROVE_TERMS.format(id=loan_id))


async def _approve(bot: Bot, session: AsyncSession, redis: Redis, user_id: int, loan_id: int, terms: str | None) -> str:
    try:
        loan, notices = await svc.approve(session, redis, user_id, loan_id, terms)
    except svc.BankError as exc:
        return error_text(exc)
    await send_pushes(bot, session, notices)
    return t.APPROVED.format(id=loan.id)


@router.message(BankStates.approve_terms)
async def on_approve_terms(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    loan_id = int((await state.get_data()).get("loan_id", 0))
    await state.clear()
    await message.answer(await _approve(message.bot, session, redis, message.from_user.id, loan_id, message.text or ""))


@router.callback_query(F.data.startswith(C.CB_BANK_APPROVE_PREFIX))
async def cb_approve(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    text = await _approve(callback.bot, session, redis, callback.from_user.id, _id(callback.data, C.CB_BANK_APPROVE_PREFIX), None)
    await callback.answer(text, show_alert=True)


@router.callback_query(F.data.startswith(C.CB_BANK_REJECT_PREFIX))
async def cb_reject(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    loan_id = _id(callback.data, C.CB_BANK_REJECT_PREFIX)
    try:
        notices = await svc.reject(session, redis, callback.from_user.id, loan_id)
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(t.REJECTED.format(id=loan_id), show_alert=True)
    await send_pushes(callback.bot, session, notices)


@router.callback_query(F.data == C.CB_BANK_APPS)
async def cb_apps(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    team = await svc.team_of(session, callback.from_user.id)
    if team is None:
        await callback.answer(t.ERRORS["no_bank"], show_alert=True)
        return
    await callback.answer()
    apps = [x for x in await svc.team_loans(session, team.bank.id) if x.status == C.LOAN_PENDING][:10]
    names = await _names(session, {x.borrower_id for x in apps})
    body = "".join(t.APP_TEAM_ROW.format(id=x.id, name=names.get(x.borrower_id, "—"), amount=format_number(x.amount), days=x.days,
                                         kind=f"{t.KIND_NAMES.get(x.kind, x.kind)} {pct(x.rate)}") for x in apps)
    await _edit(callback, t.APPS_SCREEN.format(body=body or t.APPS_EMPTY), kb.apps_menu([x.id for x in apps]))


# --- мой банк ----------------------------------------------------------------------------------

async def render_my_bank(session: AsyncSession, user_id: int):
    team = await svc.team_of(session, user_id)
    if team is None:
        return t.MY_BANK_NONE.format(min=format_number(BANK_MIN_CAPITAL), members=BANK_MEMBERS_MAX), kb.my_bank_menu(False, False, 0)
    b = team.bank
    lent, n, reserved = await svc.lent_out(session, b.id)
    loans = await svc.team_loans(session, b.id)
    names = await _names(session, {x.borrower_id for x in loans} | {b.owner_id, *team.members})
    open_loans = [x for x in loans if x.status in C.LOAN_OPEN]
    apps = sum(1 for x in loans if x.status == C.LOAN_PENDING)
    lines = "".join(t.MY_BANK_LOAN.format(id=x.id, name=names.get(x.borrower_id, "—"), debt=format_number(x.debt), due=date_label(x.due_at),
                                          mark=t.MY_BANK_MARK.get(x.status, "")) for x in open_loans[:15])
    text = t.MY_BANK.format(
        name=names.get(b.owner_id, "—"), role="" if team.is_owner else t.MY_BANK_MEMBER, capital=format_number(b.capital), lent=format_number(lent),
        open=n, reserved=format_number(reserved), kinds=kinds_short(b.fixed_rate, b.hourly_rate), min=b.min_days, max=b.max_days,
        penalty=f"{pct(b.penalty_rate)}/ч" if b.penalty_rate else "нет", earned=format_number(b.earned_total),
        members=", ".join(names.get(m, "—") for m in team.members) or "нет", loans=lines,
    )
    return text, kb.my_bank_menu(True, team.is_owner, apps)


@router.callback_query(F.data == C.CB_BANK_MY)
async def cb_my(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    text, markup = await render_my_bank(session, callback.from_user.id)
    await _edit(callback, text, markup)


async def _ask(callback: CallbackQuery, state: FSMContext, st, text: str) -> None:
    await callback.answer()
    await state.set_state(st)
    await _edit(callback, text, kb.back_menu(C.CB_BANK_MY))


def terms_prompt() -> str:
    return t.ASK_TERMS.format(fixed=f"{pct(BANK_FIXED_MIN)}–{pct(BANK_FIXED_MAX)}", hourly=f"{pct(BANK_HOURLY_MIN)}–{pct(BANK_HOURLY_MAX)}",
                              penalty=pct(BANK_PENALTY_MAX), days_min=BANK_DAYS_MIN, days_max=BANK_DAYS_MAX)


@router.callback_query(F.data == C.CB_BANK_CREATE)
async def cb_create(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    coins = await _coins(session, callback.from_user.id)
    await _ask(callback, state, BankStates.create_capital, t.ASK_CAPITAL.format(min=format_number(BANK_MIN_CAPITAL), coins=format_number(coins)))


@router.message(BankStates.create_capital)
async def on_create_capital(message: Message, state: FSMContext) -> None:
    amount = _number(message.text)
    if amount is None or amount < BANK_MIN_CAPITAL:
        await message.answer(t.ERRORS["min_capital"].format(value=format_number(BANK_MIN_CAPITAL)))
        return
    await state.update_data(capital=amount)
    await state.set_state(BankStates.create_terms)
    await message.answer(terms_prompt(), reply_markup=kb.back_menu(C.CB_BANK_MY))


async def _after(message: Message, session: AsyncSession, text: str) -> None:
    await message.answer(text)
    screen, markup = await render_my_bank(session, message.from_user.id)
    await message.answer(screen, reply_markup=markup)


@router.message(BankStates.create_terms)
async def on_create_terms(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    terms = parse_terms(message.text)
    if terms is None:
        await message.answer(t.BAD_TERMS)
        return
    capital = int((await state.get_data()).get("capital", 0))
    try:
        bank = await svc.create_bank(session, redis, message.from_user.id, capital, *terms)
    except svc.BankError as exc:
        await message.answer(error_text(exc))
        return
    await state.clear()
    await _after(message, session, t.CREATED.format(capital=format_number(bank.capital)))


@router.callback_query(F.data == C.CB_BANK_TERMS)
async def cb_terms(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask(callback, state, BankStates.terms, terms_prompt())


@router.message(BankStates.terms)
async def on_terms(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    terms = parse_terms(message.text)
    if terms is None:
        await message.answer(t.BAD_TERMS)
        return
    try:
        await svc.set_terms(session, redis, message.from_user.id, *terms)
    except svc.BankError as exc:
        await message.answer(error_text(exc))
        return
    await state.clear()
    await _after(message, session, t.TERMS_SET)


@router.callback_query(F.data == C.CB_BANK_DEPOSIT)
async def cb_deposit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _ask(callback, state, BankStates.deposit, t.ASK_DEPOSIT.format(coins=format_number(await _coins(session, callback.from_user.id))))


@router.callback_query(F.data == C.CB_BANK_WITHDRAW)
async def cb_withdraw(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    bank = await svc.get_bank(session, callback.from_user.id)
    await _ask(callback, state, BankStates.withdraw, t.ASK_WITHDRAW.format(capital=format_number(bank.capital if bank else 0)))


@router.message(BankStates.deposit)
@router.message(BankStates.withdraw)
async def on_capital_move(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    if amount is None:
        await message.answer(t.BAD_NUMBER)
        return
    is_deposit = await state.get_state() == BankStates.deposit.state
    try:
        capital = await (svc.add_capital if is_deposit else svc.withdraw)(session, redis, message.from_user.id, amount)
    except svc.BankError as exc:
        await message.answer(error_text(exc))
        return
    await state.clear()
    await _after(message, session, (t.DEPOSITED if is_deposit else t.WITHDRAWN).format(capital=format_number(capital)))


async def _show_members(callback: CallbackQuery, session: AsyncSession) -> bool:
    team = await svc.team_of(session, callback.from_user.id)
    if team is None or not team.is_owner:
        await callback.answer(t.ERRORS["owner_only"], show_alert=True)
        return False
    names = await _names(session, set(team.members))
    members = [(m, names.get(m, "—")) for m in team.members]
    body = "\n".join(f"• {n}" for _, n in members) or t.MEMBERS_EMPTY
    await _edit(callback, t.MEMBERS_SCREEN.format(body=body), kb.members_menu(members, len(members) < BANK_MEMBERS_MAX))
    return True


@router.callback_query(F.data == C.CB_BANK_MEMBERS)
async def cb_members(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if await _show_members(callback, session):
        await callback.answer()


@router.callback_query(F.data == C.CB_BANK_MEMBER_ADD)
async def cb_member_add(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask(callback, state, BankStates.member, t.ASK_MEMBER.format(max=BANK_MEMBERS_MAX))


@router.message(BankStates.member)
async def on_member(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    try:
        _, name = await svc.add_member(session, redis, message.from_user.id, message.text or "")
    except svc.BankError as exc:
        await message.answer(error_text(exc))
        return
    await state.clear()
    await _after(message, session, t.MEMBER_ADDED.format(name=esc(name)))


@router.callback_query(F.data.startswith(C.CB_BANK_MEMBER_DEL_PREFIX))
async def cb_member_del(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        await svc.remove_member(session, redis, callback.from_user.id, _id(callback.data, C.CB_BANK_MEMBER_DEL_PREFIX))
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    if await _show_members(callback, session):
        await callback.answer()


@router.callback_query(F.data == C.CB_BANK_CLOSE)
async def cb_close(callback: CallbackQuery, session: AsyncSession) -> None:
    bank = await svc.get_bank(session, callback.from_user.id)
    if bank is None:
        await callback.answer(t.ERRORS["owner_only"], show_alert=True)
        return
    await callback.answer()
    await _edit(callback, t.CLOSE_ASK.format(capital=format_number(bank.capital)), kb.close_menu())


@router.callback_query(F.data == C.CB_BANK_CLOSE_YES)
async def cb_close_yes(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        capital = await svc.close_bank(session, redis, callback.from_user.id)
    except svc.BankError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await _edit(callback, t.CLOSED.format(capital=format_number(capital)), kb.back_menu(C.CB_BANK_OPEN))


# --- пуши --------------------------------------------------------------------------------------

async def send_pushes(bot: Bot, session: AsyncSession, notices) -> None:
    """Пуши по кредитам — без выключателя (деньги, договоры, заморозка, рабство). Заявки — с кнопками одобрения,
    договоры — с кнопками подписи."""
    if not notices:
        return
    loan_ids = {n.loan_id for n in notices if n.loan_id}
    loans = {x.id: x for x in (await session.scalars(select(BankLoan).where(BankLoan.id.in_(loan_ids)))).all()} if loan_ids else {}
    names = await _names(session, {x.borrower_id for x in loans.values()} | {x.lender_id for x in loans.values()})
    for n in notices:
        loan = loans.get(n.loan_id)
        markup = None
        try:
            if n.code == "offer" and loan is not None:
                text, markup = contract_text(loan, names.get(loan.lender_id, "—"), names.get(loan.borrower_id, "—")), kb.offer_menu(loan.id)
            elif n.code == "apply" and loan is not None:
                text = t.PUSHES["apply"].format(id=loan.id, borrower=names.get(loan.borrower_id, "—"), amount=format_number(loan.amount), days=loan.days,
                                                kind=f"{t.KIND_NAMES.get(loan.kind, loan.kind)} {pct(loan.rate)}")
                markup = kb.app_menu(loan.id)
            else:
                values = {k: format_number(v) if isinstance(v, int) else v for k, v in n.values.items()}
                values.setdefault("id", n.loan_id)
                text = t.PUSHES[n.code].format(**values)
                if n.code == "frozen":
                    markup = kb.frozen_menu()
            await bot.send_message(n.user_id, text, reply_markup=markup)
        except Exception:  # noqa: BLE001 — игрок заблокировал бота и т.п.
            log.info("Bank push %s to %s failed", n.code, n.user_id)
