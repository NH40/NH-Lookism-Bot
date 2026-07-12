"""Блэкджек против дилера."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.casino.common import CASINO_RESOURCES
from app.services.bank.casino.blackjack_service import (
    blackjack_service, format_hand, format_card, hand_value,
)
from app.services.cooldown_service import cooldown_service
from app.utils.formatters import fmt_num
from app.utils.safe_edit import safe_edit
from app.utils.keyboards.common import back_kb

router = Router()


class BlackjackFSM(StatesGroup):
    waiting_amount = State()
    playing = State()


def _bj_main_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    for res, label in CASINO_RESOURCES.items():
        builder.row(InlineKeyboardButton(text=f"🃏 Ставка: {label}", callback_data=f"bj_pick:{res}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
    return builder.as_markup()


def _play_kb(hand: dict, balance: int) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    row = [
        InlineKeyboardButton(text="➕ Взять карту", callback_data="bj_hit"),
        InlineKeyboardButton(text="🛑 Остановиться", callback_data="bj_stand"),
    ]
    builder.row(*row)
    if len(hand["player_cards"]) == 2 and not hand["doubled"] and hand["bet"] <= balance:
        builder.row(InlineKeyboardButton(text="💰 Удвоить", callback_data="bj_double"))
    return builder.as_markup()


def _render_playing(hand: dict) -> str:
    label = CASINO_RESOURCES[hand["resource"]]
    dealer_open = hand["dealer_cards"][0]
    return (
        f"🃏 <b>Блэкджек</b>\n\n"
        f"Ставка: {fmt_num(hand['total_stake'])} {label}\n\n"
        f"Дилер: {format_card(dealer_open)} 🂠\n"
        f"Вы: {format_hand(hand['player_cards'])} (<b>{hand_value(hand['player_cards'])}</b>)"
    )


_OUTCOME_TEXT = {
    "blackjack": "🎉 <b>Блэкджек!</b>",
    "push_natural": "🤝 <b>Ничья (оба блэкджек)</b>",
    "win": "🎉 <b>Победа!</b>",
    "push": "🤝 <b>Ничья</b>",
    "loss": "😔 <b>Поражение</b>",
    "bust": "💥 <b>Перебор!</b>",
}


def _render_finished(hand: dict, outcome: str) -> str:
    label = CASINO_RESOURCES[hand["resource"]]
    stake = hand["total_stake"]
    payout = hand.get("payout", 0)
    profit = payout - stake
    profit_line = f"+{fmt_num(profit)} {label}" if profit >= 0 else f"{fmt_num(profit)} {label}"
    return (
        f"{_OUTCOME_TEXT.get(outcome, outcome)}\n\n"
        f"Дилер: {format_hand(hand['dealer_cards'])} (<b>{hand_value(hand['dealer_cards'])}</b>)\n"
        f"Вы: {format_hand(hand['player_cards'])} (<b>{hand_value(hand['player_cards'])}</b>)\n\n"
        f"Ставка: {fmt_num(stake)} {label}\n"
        f"Итог: {profit_line}"
    )


def _finish_kb(resource: str) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🃏 Сыграть снова", callback_data=f"bj_pick:{resource}"))
    builder.row(InlineKeyboardButton(text="◀️ В казино", callback_data="bank_casino"))
    return builder.as_markup()


@router.callback_query(F.data == "bank_casino_blackjack")
async def cb_bj_menu(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    await safe_edit(cb.message, "🃏 <b>Блэкджек</b>\n\nВыберите ресурс для ставки:", reply_markup=_bj_main_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("bj_pick:"))
async def cb_bj_pick(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    resource = cb.data.split(":")[1]
    if resource not in CASINO_RESOURCES:
        await cb.answer("❌ Неизвестный ресурс.", show_alert=True)
        return

    label = CASINO_RESOURCES[resource]
    balance = getattr(user, resource, 0)

    await state.set_state(BlackjackFSM.waiting_amount)
    await state.update_data(resource=resource)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_casino_blackjack"))
    await safe_edit(
        cb.message,
        f"🃏 <b>Ставка: {label}</b>\n\nВаш баланс: <b>{fmt_num(balance)}</b>\n\nВведите размер ставки:",
        reply_markup=cancel_kb.as_markup(),
    )
    await cb.answer()


@router.message(BlackjackFSM.waiting_amount)
async def msg_bj_bet(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    resource = data.get("resource", "nh_coins")

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_casino_blackjack"), parse_mode="HTML")
        return

    lock_key = cooldown_service.blackjack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("⏳ Подождите, предыдущее действие ещё обрабатывается.", reply_markup=back_kb("bank_casino_blackjack"))
        return

    result = await blackjack_service.start(session, user, resource, amount)

    if not result.get("ok"):
        await state.clear()
        builder = InlineKeyboardBuilder()
        if result.get("x3_warn"):
            builder.row(InlineKeyboardButton(text="🔄 Изменить ставку", callback_data=f"bj_pick:{resource}"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino_blackjack"))
        await message.answer(result["msg"], reply_markup=builder.as_markup(), parse_mode="HTML")
        return

    hand = result["hand"]
    if result["finished"]:
        await state.clear()
        await message.answer(
            _render_finished(hand, result["outcome"]),
            reply_markup=_finish_kb(resource),
            parse_mode="HTML",
        )
        return

    await state.set_state(BlackjackFSM.playing)
    await state.update_data(hand=hand)
    balance = getattr(user, resource, 0)
    await message.answer(_render_playing(hand), reply_markup=_play_kb(hand, balance), parse_mode="HTML")


async def _finish_and_render(cb: CallbackQuery, state: FSMContext, hand: dict, outcome: str):
    await state.clear()
    await safe_edit(cb.message, _render_finished(hand, outcome), reply_markup=_finish_kb(hand["resource"]))


@router.callback_query(F.data == "bj_hit", BlackjackFSM.playing)
async def cb_bj_hit(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    lock_key = cooldown_service.blackjack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    data = await state.get_data()
    hand = data.get("hand")
    if not hand:
        await cb.answer("❌ Раздача не найдена.", show_alert=True)
        return

    result = await blackjack_service.hit(session, user, hand)
    if result["finished"]:
        await _finish_and_render(cb, state, hand, "bust")
        await cb.answer()
        return

    await state.update_data(hand=hand)
    balance = getattr(user, hand["resource"], 0)
    await safe_edit(cb.message, _render_playing(hand), reply_markup=_play_kb(hand, balance))
    await cb.answer()


@router.callback_query(F.data == "bj_stand", BlackjackFSM.playing)
async def cb_bj_stand(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    lock_key = cooldown_service.blackjack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    data = await state.get_data()
    hand = data.get("hand")
    if not hand:
        await cb.answer("❌ Раздача не найдена.", show_alert=True)
        return

    result = await blackjack_service.stand(session, user, hand)
    await _finish_and_render(cb, state, hand, result["outcome"])
    await cb.answer()


@router.callback_query(F.data == "bj_double", BlackjackFSM.playing)
async def cb_bj_double(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    lock_key = cooldown_service.blackjack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подождите...", show_alert=True)
        return

    data = await state.get_data()
    hand = data.get("hand")
    if not hand:
        await cb.answer("❌ Раздача не найдена.", show_alert=True)
        return

    result = await blackjack_service.double(session, user, hand)
    if not result.get("ok"):
        await cb.answer(result["msg"], show_alert=True)
        return

    await _finish_and_render(cb, state, hand, result["outcome"])
    await cb.answer()
