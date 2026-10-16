"""Донат и чёрный рынок (хендлеры). Вход — /donate и «💎 Донат» в настройках.
Пополнение — как в UAP: инвойс ЮKassa через Telegram Payments, зачисление — `handlers/payment`."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.development import MAX_LEVEL
from bot.config.donate import DONATE_MAX_RUB, DONATE_MIN_RUB, DONATE_PRESETS_RUB
from bot.services.admin.live_config import get as live_get
from bot.config.settings import get_settings
from bot.constant.donate import (
    CB_DONATE_CUSTOM,
    CB_DONATE_OPEN,
    CB_DONATE_PRESET_PREFIX,
    CB_MARKET_BODY,
    CB_MARKET_BODY_BUY,
    CB_MARKET_ITEM_PREFIX,
    CB_MARKET_KIND_PREFIX,
    CB_MARKET_LEVEL_PREFIX,
    CB_MARKET_OPEN,
    CB_MARKET_UNLOCK_PREFIX,
    DONATE_KINDS,
    PAYLOAD_DONATE_PREFIX,
)
from bot.db.repositories import donate as donate_repo
from bot.keyboards.donate import back_to_donate, body_menu, donate_menu, item_menu, kind_menu, market_menu
from bot.services.donate import (
    CATALOG,
    AlreadyBoughtError,
    DonateBusyError,
    MaxLevelError,
    NotEnoughDonateError,
    NotUnlockedError,
    UnknownItemError,
    balance,
    buy_level,
    buy_second_body,
    buy_unlock,
    item_view,
    market,
)
from bot.services.gang import get_gang
from bot.states.donate import DonateStates
from bot.texts.donate import (
    ALREADY_ALERT,
    BODY_BOUGHT_ALERT,
    BODY_NONE,
    BODY_OWNED,
    BODY_SCREEN,
    BODY_SCREEN_OWNED,
    BOUGHT_ALERT,
    BUSY_ALERT,
    CUSTOM_INVALID,
    CUSTOM_PROMPT,
    DONATE_SCREEN,
    INVOICE_DESCRIPTION,
    INVOICE_LABEL,
    INVOICE_TITLE,
    ITEM_HINT,
    ITEM_MAX,
    ITEM_NEXT_LEVEL,
    ITEM_NEXT_UNLOCK,
    ITEM_SCREEN,
    KIND_EMOJI,
    KIND_SCREEN,
    KIND_SCREEN_TAIL,
    MARKET_SCREEN,
    MAX_ALERT,
    NOT_CONFIGURED_ALERT,
    NOT_ENOUGH_ALERT,
    NOT_UNLOCKED_ALERT,
)
from bot.texts.genius import GENIUS_NAMES
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="donate")

_KOPECKS_PER_RUB = 100
NAMES = {"genius": GENIUS_NAMES, "path": PATH_NAMES, "tech": TECHNIQUE_NAMES}


async def _send_invoice(bot: Bot, chat_id: int, amount_rub: int) -> None:
    await bot.send_invoice(
        chat_id=chat_id,
        title=INVOICE_TITLE,
        description=INVOICE_DESCRIPTION.format(amount=amount_rub),
        payload=f"{PAYLOAD_DONATE_PREFIX}{amount_rub}",
        provider_token=get_settings().yookassa_provider_token,
        currency="RUB",
        prices=[LabeledPrice(label=INVOICE_LABEL.format(amount=amount_rub), amount=amount_rub * _KOPECKS_PER_RUB)],
    )


async def _donate_text(session: AsyncSession, user_id: int) -> str:
    return DONATE_SCREEN.format(balance=format_number(await balance(session, user_id)))


@router.message(Command("donate"))
async def cmd_donate(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if await get_gang(session, message.from_user.id) is None:
        await message.answer(NOT_ONBOARDED)
        return
    await message.answer(await _donate_text(session, message.from_user.id), reply_markup=donate_menu())


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_DONATE_OPEN)
async def cb_donate(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    await safe_edit_text(callback.message, await _donate_text(session, callback.from_user.id), reply_markup=donate_menu())


@router.callback_query(F.data.startswith(CB_DONATE_PRESET_PREFIX))
async def cb_preset(callback: CallbackQuery, bot: Bot) -> None:
    raw = callback.data.removeprefix(CB_DONATE_PRESET_PREFIX)
    if not raw.isdigit() or int(raw) not in DONATE_PRESETS_RUB:
        await callback.answer()
        return
    if not get_settings().yookassa_provider_token:
        await callback.answer(NOT_CONFIGURED_ALERT, show_alert=True)
        return
    await callback.answer()
    await _send_invoice(bot, callback.message.chat.id, int(raw))


@router.callback_query(F.data == CB_DONATE_CUSTOM)
async def cb_custom(callback: CallbackQuery, state: FSMContext) -> None:
    if not get_settings().yookassa_provider_token:
        await callback.answer(NOT_CONFIGURED_ALERT, show_alert=True)
        return
    await state.set_state(DonateStates.waiting_amount)
    await callback.answer()
    await safe_edit_text(
        callback.message, CUSTOM_PROMPT.format(min=DONATE_MIN_RUB, max=format_number(DONATE_MAX_RUB)), reply_markup=back_to_donate()
    )


@router.message(StateFilter(DonateStates.waiting_amount))
async def on_custom_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit() or not DONATE_MIN_RUB <= int(raw) <= DONATE_MAX_RUB:
        await message.answer(
            CUSTOM_INVALID.format(min=DONATE_MIN_RUB, max=format_number(DONATE_MAX_RUB)), reply_markup=back_to_donate()
        )
        return
    await state.clear()
    await _send_invoice(bot, message.chat.id, int(raw))


# --- чёрный рынок ---


async def _show_market(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    body = await donate_repo.body_state(session, user_id)
    text = MARKET_SCREEN.format(
        balance=format_number(await balance(session, user_id)), body=BODY_OWNED if body and body[0] else BODY_NONE
    )
    await safe_edit_text(callback.message, text, reply_markup=market_menu())


@router.callback_query(F.data == CB_MARKET_OPEN)
async def cb_market(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    await _show_market(callback, session)


async def _show_body(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    body = await donate_repo.body_state(session, user_id)
    if body and body[0]:
        await safe_edit_text(callback.message, BODY_SCREEN_OWNED, reply_markup=body_menu(None))
        return
    body_price = live_get("second_body_price")
    text = BODY_SCREEN.format(price=format_number(body_price), balance=format_number(await balance(session, user_id)))
    await safe_edit_text(callback.message, text, reply_markup=body_menu(body_price))


@router.callback_query(F.data == CB_MARKET_BODY)
async def cb_body(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await _show_body(callback, session)


async def _alert_error(callback: CallbackQuery, exc: Exception) -> None:
    if isinstance(exc, DonateBusyError):
        await callback.answer(BUSY_ALERT)
    elif isinstance(exc, NotEnoughDonateError):
        await callback.answer(
            NOT_ENOUGH_ALERT.format(price=format_number(exc.price), balance=format_number(exc.balance)), show_alert=True
        )
    else:
        alerts = {AlreadyBoughtError: ALREADY_ALERT, NotUnlockedError: NOT_UNLOCKED_ALERT, MaxLevelError: MAX_ALERT}
        await callback.answer(alerts.get(type(exc), ALREADY_ALERT), show_alert=True)


_BUY_ERRORS = (DonateBusyError, NotEnoughDonateError, AlreadyBoughtError, NotUnlockedError, MaxLevelError, UnknownItemError)


@router.callback_query(F.data == CB_MARKET_BODY_BUY)
async def cb_body_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    try:
        await buy_second_body(session, redis, callback.from_user.id)
    except _BUY_ERRORS as exc:
        await _alert_error(callback, exc)
        return
    await callback.answer(BODY_BOUGHT_ALERT, show_alert=True)
    await _show_body(callback, session)


async def _show_kind(callback: CallbackQuery, session: AsyncSession, kind: str) -> None:
    user_id = callback.from_user.id
    items = await market(session, user_id, kind)
    text = KIND_SCREEN[kind] + KIND_SCREEN_TAIL.format(balance=format_number(await balance(session, user_id)))
    await safe_edit_text(callback.message, text, reply_markup=kind_menu(kind, items, NAMES[kind]))


@router.callback_query(F.data.startswith(CB_MARKET_KIND_PREFIX))
async def cb_kind(callback: CallbackQuery, session: AsyncSession) -> None:
    kind = callback.data.removeprefix(CB_MARKET_KIND_PREFIX)
    if kind not in DONATE_KINDS or not await _guard(callback, session):
        await callback.answer()
        return
    await callback.answer()
    await _show_kind(callback, session, kind)


def _parse(data: str, prefix: str) -> tuple[str, str] | None:
    kind, _, code = data.removeprefix(prefix).partition(":")
    return (kind, code) if kind in CATALOG and code in CATALOG[kind] else None


async def _show_item(callback: CallbackQuery, session: AsyncSession, kind: str, code: str) -> None:
    user_id = callback.from_user.id
    item = item_view(kind, code, await donate_repo.floor(session, user_id, kind, code))
    if item.next_price is None:
        next_line = ITEM_MAX
    elif item.level == 0:
        next_line = ITEM_NEXT_UNLOCK.format(price=format_number(item.next_price))
    else:
        next_line = ITEM_NEXT_LEVEL.format(level=item.level + 1, price=format_number(item.next_price))
    text = ITEM_SCREEN.format(
        emoji=KIND_EMOJI[kind], name=NAMES[kind].get(code, code), level=item.level, max=MAX_LEVEL, next_line=next_line,
        balance=format_number(await balance(session, user_id)), hint=ITEM_HINT[kind],
    )
    await safe_edit_text(callback.message, text, reply_markup=item_menu(item))


@router.callback_query(F.data.startswith(CB_MARKET_ITEM_PREFIX))
async def cb_item(callback: CallbackQuery, session: AsyncSession) -> None:
    parsed = _parse(callback.data, CB_MARKET_ITEM_PREFIX)
    if parsed is None or not await _guard(callback, session):
        await callback.answer()
        return
    await callback.answer()
    await _show_item(callback, session, *parsed)


@router.callback_query(F.data.startswith(CB_MARKET_UNLOCK_PREFIX) | F.data.startswith(CB_MARKET_LEVEL_PREFIX))
async def cb_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    is_unlock = callback.data.startswith(CB_MARKET_UNLOCK_PREFIX)
    parsed = _parse(callback.data, CB_MARKET_UNLOCK_PREFIX if is_unlock else CB_MARKET_LEVEL_PREFIX)
    if parsed is None or not await _guard(callback, session):
        await callback.answer()
        return
    kind, code = parsed
    try:
        await (buy_unlock if is_unlock else buy_level)(session, redis, callback.from_user.id, kind, code)
    except _BUY_ERRORS as exc:
        await _alert_error(callback, exc)
        return
    await callback.answer(BOUGHT_ALERT)
    await _show_item(callback, session, kind, code)
