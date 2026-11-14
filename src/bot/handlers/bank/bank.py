"""Банки игроков и кредиты (хендлеры). Вход — «💳 Кредиты» в магазине. `send_pushes()` — пуши фонового прохода
(`main.py`)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.bank import BANK_DAYS_MAX, BANK_DAYS_MIN, BANK_FREEZE_DAYS, BANK_MIN_CAPITAL, BANK_MIN_LOAN, BANK_RATE_MAX, BANK_RATE_MIN
from bot.constant.bank import (
    CB_BANK_CLOSE,
    CB_BANK_CLOSE_YES,
    CB_BANK_CONFIRM,
    CB_BANK_CREATE,
    CB_BANK_DAYS_PREFIX,
    CB_BANK_DEPOSIT,
    CB_BANK_LOANS,
    CB_BANK_MY,
    CB_BANK_OPEN,
    CB_BANK_PAGE_PREFIX,
    CB_BANK_REPAY_ALL_PREFIX,
    CB_BANK_REPAY_PREFIX,
    CB_BANK_TAKE_PREFIX,
    CB_BANK_TERMS,
    CB_BANK_VIEW_PREFIX,
    CB_BANK_WITHDRAW,
    LOAN_FROZEN,
)
from bot.db.models.gang import Gang
from bot.db.models.user import User
from bot.keyboards.bank import (
    back_menu,
    card_menu,
    close_menu,
    confirm_menu,
    days_menu,
    list_menu,
    loans_menu,
    my_bank_menu,
)
from bot.services.bank import (
    BankError,
    add_capital,
    bank_card,
    close_bank,
    create_bank,
    get_bank,
    issued_loans,
    lent_out,
    list_banks,
    my_loans,
    repay,
    set_terms,
    take_loan,
    withdraw,
)
from bot.services.gang import get_gang
from bot.states.bank import BankStates
from bot.texts.bank import (
    ASK_AMOUNT,
    ASK_CAPITAL,
    ASK_DAYS,
    ASK_DEPOSIT,
    ASK_REPAY,
    ASK_TERMS,
    ASK_WITHDRAW,
    BAD_NUMBER,
    BAD_TERMS,
    CARD,
    CLOSE_ASK,
    CLOSED,
    CONFIRM,
    CREATED,
    DEPOSITED,
    ERRORS,
    LIST_EMPTY,
    LIST_HINT,
    LIST_SCREEN,
    LOAN_DUE,
    LOAN_FROZEN as LOAN_FROZEN_TEXT,
    LOAN_ROW,
    LOANS_EMPTY,
    LOANS_SCREEN,
    MY_BANK,
    MY_BANK_FROZEN,
    MY_BANK_LOAN,
    MY_BANK_NONE,
    PUSHES,
    REPAID_FULL,
    REPAID_PART,
    REPAID_UNFROZEN,
    TAKEN,
    TERMS_SET,
    WITHDRAWN,
)
from bot.texts.bank.bank import BANK_ROW_BTN
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

log = logging.getLogger(__name__)
router = Router(name="bank")


def rate_label(rate: float) -> str:
    return f"{rate * 100:.1f}".rstrip("0").rstrip(".") + "%"


def _short(n: int) -> str:
    for size, suffix in ((10**12, "трлн"), (10**9, "млрд"), (10**6, "млн"), (10**3, "тыс")):
        if n >= size:
            return f"{n / size:.1f}".rstrip("0").rstrip(".") + " " + suffix
    return str(n)


def _date(moment: datetime) -> str:
    return (moment + timedelta(hours=3)).strftime("%d.%m %H:%M") + " МСК"


def _left(moment: datetime) -> str:
    return format_countdown(max(0, int((moment - datetime.now(timezone.utc)).total_seconds())))


def _error(exc: BankError) -> str:
    value = exc.value if isinstance(exc.value, float) else format_number(int(exc.value))
    return ERRORS.get(exc.code, exc.code).format(value=value)


def _number(text: str | None) -> int | None:
    raw = (text or "").replace(" ", "").replace(",", "").replace("_", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def parse_terms(text: str | None) -> tuple[float, int, int] | None:
    """«5 3 14» → (0.05, 3, 14)."""
    parts = (text or "").replace(",", ".").replace("%", " ").split()
    if len(parts) != 3:
        return None
    try:
        return float(parts[0]) / 100, int(parts[1]), int(parts[2])
    except ValueError:
        return None


async def _coins(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(User.nh_coins).where(User.id == user_id)) or 0)


async def _names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = await session.execute(select(Gang.user_id, Gang.name).where(Gang.user_id.in_(ids)))
    return {uid: esc(name) for uid, name in rows.all()}


# --- список и карточка банка ------------------------------------------------------------------

async def _show_list(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    rows, more = await list_banks(session, callback.from_user.id, page)
    body = LIST_HINT if rows else LIST_EMPTY
    buttons = [(BANK_ROW_BTN.format(name=r.owner_name[:16], rate=rate_label(r.rate), min=r.min_days, max=r.max_days,
                                    capital=_short(r.capital)), r.id) for r in rows]
    await safe_edit_text(callback.message, LIST_SCREEN.format(freeze=BANK_FREEZE_DAYS, body=body), reply_markup=list_menu(buttons, page, more))


@router.callback_query(F.data == CB_BANK_OPEN)
async def cb_bank_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await _show_list(callback, session, 0)


@router.callback_query(F.data.startswith(CB_BANK_PAGE_PREFIX))
async def cb_bank_page(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_BANK_PAGE_PREFIX)
    await callback.answer()
    await _show_list(callback, session, int(raw) if raw.isdigit() else 0)


@router.callback_query(F.data.startswith(CB_BANK_VIEW_PREFIX))
async def cb_bank_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    raw = callback.data.removeprefix(CB_BANK_VIEW_PREFIX)
    card = await bank_card(session, int(raw)) if raw.isdigit() else None
    if card is None:
        await callback.answer(ERRORS["no_bank"], show_alert=True)
        return
    await callback.answer()
    text = CARD.format(name=esc(card.owner_name), rate=rate_label(card.rate), min=card.min_days, max=card.max_days,
                       capital=format_number(card.capital), open=card.open_loans, lent=format_number(card.lent_total))
    can_take = card.owner_id != callback.from_user.id and card.capital >= BANK_MIN_LOAN
    await safe_edit_text(callback.message, text, reply_markup=card_menu(card.id, can_take))


# --- взять кредит -------------------------------------------------------------------------------

@router.callback_query(F.data.startswith(CB_BANK_TAKE_PREFIX))
async def cb_bank_take(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_BANK_TAKE_PREFIX)
    card = await bank_card(session, int(raw)) if raw.isdigit() else None
    if card is None:
        await callback.answer(ERRORS["no_bank"], show_alert=True)
        return
    await callback.answer()
    await state.set_state(BankStates.take_amount)
    await state.update_data(bank_id=card.id)
    await safe_edit_text(callback.message, ASK_AMOUNT.format(min=format_number(BANK_MIN_LOAN), max=format_number(card.capital)),
                         reply_markup=back_menu(f"{CB_BANK_VIEW_PREFIX}{card.id}"))


@router.message(BankStates.take_amount)
async def on_take_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    amount = _number(message.text)
    data = await state.get_data()
    card = await bank_card(session, data.get("bank_id", 0))
    if card is None:
        await state.clear()
        await message.answer(ERRORS["no_bank"])
        return
    if amount is None:
        await message.answer(BAD_NUMBER)
        return
    if amount > card.capital or amount < BANK_MIN_LOAN:
        await message.answer(ERRORS["no_capital"].format(value=format_number(card.capital)) if amount > card.capital
                             else ERRORS["min_loan"].format(value=format_number(BANK_MIN_LOAN)))
        return
    await state.update_data(amount=amount)
    await state.set_state(None)
    await message.answer(ASK_DAYS.format(amount=format_number(amount)), reply_markup=days_menu(card.min_days, card.max_days, card.id))


@router.callback_query(F.data.startswith(CB_BANK_DAYS_PREFIX))
async def cb_bank_days(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    raw = callback.data.removeprefix(CB_BANK_DAYS_PREFIX)
    card = await bank_card(session, data.get("bank_id", 0))
    if card is None or not data.get("amount") or not raw.isdigit():
        await callback.answer(ERRORS["no_bank"], show_alert=True)
        return
    days, amount = int(raw), int(data["amount"])
    await state.update_data(days=days)
    await callback.answer()
    per_day = max(1, round(amount * card.rate))
    text = CONFIRM.format(name=esc(card.owner_name), amount=format_number(amount), days=days, rate=rate_label(card.rate),
                          per_day=format_number(per_day), total=format_number(amount + per_day * days),
                          due=_date(datetime.now(timezone.utc) + timedelta(days=days)))
    await safe_edit_text(callback.message, text, reply_markup=confirm_menu(card.id))


@router.callback_query(F.data == CB_BANK_CONFIRM)
async def cb_bank_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    data = await state.get_data()
    if not all(data.get(k) for k in ("bank_id", "amount", "days")):
        await callback.answer(ERRORS["no_bank"], show_alert=True)
        return
    try:
        loan = await take_loan(session, redis, callback.from_user.id, int(data["bank_id"]), int(data["amount"]), int(data["days"]))
    except BankError as exc:
        await callback.answer(_error(exc), show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, TAKEN.format(amount=format_number(loan.amount), due=_date(loan.due_at), debt=format_number(loan.debt)),
                         reply_markup=back_menu(CB_BANK_LOANS))


# --- мои кредиты ------------------------------------------------------------------------------

async def render_loans(session: AsyncSession, user_id: int) -> tuple[str, list[int]]:
    loans = await my_loans(session, user_id)
    names = await _names(session, {loan.lender_id for loan in loans})
    rows = []
    for loan in loans:
        when = (LOAN_FROZEN_TEXT.format(until=_date(loan.frozen_until), left=_left(loan.frozen_until))
                if loan.status == LOAN_FROZEN and loan.frozen_until else
                LOAN_DUE.format(due=_date(loan.due_at), left=_left(loan.due_at), rate=rate_label(loan.rate)))
        rows.append(LOAN_ROW.format(id=loan.id, name=names.get(loan.lender_id, "—"), debt=format_number(loan.debt),
                                    principal=format_number(loan.principal), interest=format_number(loan.interest), when=when))
    return LOANS_SCREEN.format(body="\n".join(rows) if rows else LOANS_EMPTY), [loan.id for loan in loans]


@router.callback_query(F.data == CB_BANK_LOANS)
async def cb_bank_loans(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    text, ids = await render_loans(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=loans_menu(ids))


async def _repay(session: AsyncSession, redis: Redis, user_id: int, loan_id: int, amount: int | None) -> str:
    try:
        loan, paid, unfrozen = await repay(session, redis, user_id, loan_id, amount)
    except BankError as exc:
        return _error(exc)
    if unfrozen:
        return REPAID_UNFROZEN
    if loan.debt == 0:
        return REPAID_FULL.format(id=loan.id)
    return REPAID_PART.format(paid=format_number(paid), debt=format_number(loan.debt))


@router.callback_query(F.data.startswith(CB_BANK_REPAY_ALL_PREFIX))
async def cb_bank_repay_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_BANK_REPAY_ALL_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    result = await _repay(session, redis, callback.from_user.id, int(raw), None)
    await callback.answer(result, show_alert=True)
    text, ids = await render_loans(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=loans_menu(ids))


@router.callback_query(F.data.startswith(CB_BANK_REPAY_PREFIX))
async def cb_bank_repay(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_BANK_REPAY_PREFIX)
    loans = {loan.id: loan for loan in await my_loans(session, callback.from_user.id)}
    loan = loans.get(int(raw)) if raw.isdigit() else None
    if loan is None:
        await callback.answer(ERRORS["no_loan"], show_alert=True)
        return
    await callback.answer()
    await state.set_state(BankStates.repay_amount)
    await state.update_data(loan_id=loan.id)
    await safe_edit_text(callback.message, ASK_REPAY.format(id=loan.id, debt=format_number(loan.debt),
                                                            coins=format_number(await _coins(session, callback.from_user.id))),
                         reply_markup=back_menu(CB_BANK_LOANS))


@router.message(BankStates.repay_amount)
async def on_repay_amount(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    if amount is None:
        await message.answer(BAD_NUMBER)
        return
    loan_id = int((await state.get_data()).get("loan_id", 0))
    await state.clear()
    await message.answer(await _repay(session, redis, message.from_user.id, loan_id, amount))
    text, ids = await render_loans(session, message.from_user.id)
    await message.answer(text, reply_markup=loans_menu(ids))


# --- мой банк ----------------------------------------------------------------------------------

async def render_my_bank(session: AsyncSession, user_id: int) -> tuple[str, bool]:
    bank = await get_bank(session, user_id)
    if bank is None:
        return MY_BANK_NONE.format(min=format_number(BANK_MIN_CAPITAL), rate_min=rate_label(BANK_RATE_MIN), rate_max=rate_label(BANK_RATE_MAX),
                                   days_min=BANK_DAYS_MIN, days_max=BANK_DAYS_MAX), False
    lent, n = await lent_out(session, bank.id)
    loans = await issued_loans(session, user_id)
    names = await _names(session, {loan.borrower_id for loan in loans})
    lines = "".join(MY_BANK_LOAN.format(id=loan.id, name=names.get(loan.borrower_id, "—"), debt=format_number(loan.debt), due=_date(loan.due_at),
                                        frozen=MY_BANK_FROZEN if loan.status == LOAN_FROZEN else "") for loan in loans[:15])
    return MY_BANK.format(capital=format_number(bank.capital), lent=format_number(lent), open=n, rate=rate_label(bank.rate), min=bank.min_days,
                          max=bank.max_days, earned=format_number(bank.earned_total), loans=lines), True


@router.callback_query(F.data == CB_BANK_MY)
async def cb_bank_my(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    text, has = await render_my_bank(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=my_bank_menu(has))


async def _ask(callback: CallbackQuery, state: FSMContext, st, text: str) -> None:
    await callback.answer()
    await state.set_state(st)
    await safe_edit_text(callback.message, text, reply_markup=back_menu(CB_BANK_MY))


@router.callback_query(F.data == CB_BANK_CREATE)
async def cb_bank_create(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    coins = await _coins(session, callback.from_user.id)
    await _ask(callback, state, BankStates.create_capital, ASK_CAPITAL.format(min=format_number(BANK_MIN_CAPITAL), coins=format_number(coins)))


def _terms_prompt() -> str:
    return ASK_TERMS.format(rate_min=rate_label(BANK_RATE_MIN), rate_max=rate_label(BANK_RATE_MAX), days_min=BANK_DAYS_MIN, days_max=BANK_DAYS_MAX)


@router.message(BankStates.create_capital)
async def on_create_capital(message: Message, state: FSMContext) -> None:
    amount = _number(message.text)
    if amount is None or amount < BANK_MIN_CAPITAL:
        await message.answer(ERRORS["min_capital"].format(value=format_number(BANK_MIN_CAPITAL)))
        return
    await state.update_data(capital=amount)
    await state.set_state(BankStates.create_terms)
    await message.answer(_terms_prompt(), reply_markup=back_menu(CB_BANK_MY))


@router.message(BankStates.create_terms)
async def on_create_terms(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    terms = parse_terms(message.text)
    if terms is None:
        await message.answer(BAD_TERMS)
        return
    capital = int((await state.get_data()).get("capital", 0))
    try:
        bank = await create_bank(session, redis, message.from_user.id, capital, *terms)
    except BankError as exc:
        await message.answer(_error(exc))
        return
    await state.clear()
    await message.answer(CREATED.format(capital=format_number(bank.capital), rate=rate_label(bank.rate), min=bank.min_days, max=bank.max_days))
    text, has = await render_my_bank(session, message.from_user.id)
    await message.answer(text, reply_markup=my_bank_menu(has))


@router.callback_query(F.data == CB_BANK_TERMS)
async def cb_bank_terms(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask(callback, state, BankStates.terms, _terms_prompt())


@router.message(BankStates.terms)
async def on_terms(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    terms = parse_terms(message.text)
    if terms is None:
        await message.answer(BAD_TERMS)
        return
    try:
        await set_terms(session, redis, message.from_user.id, *terms)
    except BankError as exc:
        await message.answer(_error(exc))
        return
    await state.clear()
    await message.answer(TERMS_SET)
    text, has = await render_my_bank(session, message.from_user.id)
    await message.answer(text, reply_markup=my_bank_menu(has))


@router.callback_query(F.data == CB_BANK_DEPOSIT)
async def cb_bank_deposit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _ask(callback, state, BankStates.deposit, ASK_DEPOSIT.format(coins=format_number(await _coins(session, callback.from_user.id))))


@router.callback_query(F.data == CB_BANK_WITHDRAW)
async def cb_bank_withdraw(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    bank = await get_bank(session, callback.from_user.id)
    await _ask(callback, state, BankStates.withdraw, ASK_WITHDRAW.format(capital=format_number(bank.capital if bank else 0)))


@router.message(BankStates.deposit)
@router.message(BankStates.withdraw)
async def on_capital_move(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    if amount is None:
        await message.answer(BAD_NUMBER)
        return
    is_deposit = await state.get_state() == BankStates.deposit.state
    try:
        if is_deposit:
            capital = await add_capital(session, redis, message.from_user.id, amount)
        else:
            capital = await withdraw(session, redis, message.from_user.id, amount)
    except BankError as exc:
        await message.answer(_error(exc))
        return
    await state.clear()
    await message.answer((DEPOSITED if is_deposit else WITHDRAWN).format(capital=format_number(capital)))
    text, has = await render_my_bank(session, message.from_user.id)
    await message.answer(text, reply_markup=my_bank_menu(has))


@router.callback_query(F.data == CB_BANK_CLOSE)
async def cb_bank_close(callback: CallbackQuery, session: AsyncSession) -> None:
    bank = await get_bank(session, callback.from_user.id)
    if bank is None:
        await callback.answer(ERRORS["no_bank"], show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, CLOSE_ASK.format(capital=format_number(bank.capital)), reply_markup=close_menu())


@router.callback_query(F.data == CB_BANK_CLOSE_YES)
async def cb_bank_close_yes(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        capital = await close_bank(session, redis, callback.from_user.id)
    except BankError as exc:
        await callback.answer(_error(exc), show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, CLOSED.format(capital=format_number(capital)), reply_markup=back_menu(CB_BANK_OPEN))


# --- пуши фонового прохода ---------------------------------------------------------------------

async def send_pushes(bot: Bot, notices) -> None:
    """Пуши о долгах — без выключателя: заморозка и удаление банды слишком важны, чтобы о них не знать."""
    from bot.keyboards.bank import frozen_menu

    for n in notices:
        values = {k: format_number(v) if isinstance(v, int) else v for k, v in n.values.items()}
        try:
            await bot.send_message(n.user_id, PUSHES[n.code].format(**values), reply_markup=frozen_menu() if n.code == "frozen" else None)
        except Exception:  # noqa: BLE001 — игрок заблокировал бота и т.п.
            log.info("Bank push to %s failed", n.user_id)
