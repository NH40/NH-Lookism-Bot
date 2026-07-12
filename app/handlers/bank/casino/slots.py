"""Слоты: выбор ресурса, ставка, прокрутка барабана."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.casino.common import CASINO_RESOURCES
from app.services.bank.casino.slots_service import slots_service
from app.constants.bank import SLOTS_SYMBOLS, SLOTS_SYMBOL_EMOJI, SLOTS_MULTIPLIERS
from app.utils.formatters import fmt_num
from app.utils.safe_edit import safe_edit
from app.utils.keyboards.common import back_kb

router = Router()


class SlotsFSM(StatesGroup):
    waiting_amount = State()


def _slots_main_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    for res, label in CASINO_RESOURCES.items():
        builder.row(InlineKeyboardButton(text=f"🎰 Поставить {label}", callback_data=f"slots_pick:{res}"))
    builder.row(InlineKeyboardButton(text="📜 Таблица выплат", callback_data="slots_paytable"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
    return builder.as_markup()


def _paytable_text() -> str:
    lines = ["🎰 <b>Таблица выплат</b>\n"]
    for s in SLOTS_SYMBOLS:
        emoji = SLOTS_SYMBOL_EMOJI[s]
        lines.append(f"{emoji}{emoji}{emoji} — x{SLOTS_MULTIPLIERS[s]}")
    lines.append("\nЛюбые 2 одинаковых символа — возврат ставки.")
    return "\n".join(lines)


@router.callback_query(F.data == "bank_casino_slots")
async def cb_slots_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    await safe_edit(
        cb.message,
        "🎰 <b>Слоты</b>\n\nВыберите ресурс для ставки:",
        reply_markup=_slots_main_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "slots_paytable")
async def cb_slots_paytable(cb: CallbackQuery):
    await safe_edit(cb.message, _paytable_text(), reply_markup=back_kb("bank_casino_slots"))
    await cb.answer()


@router.callback_query(F.data.startswith("slots_pick:"))
async def cb_slots_pick(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    resource = cb.data.split(":")[1]
    if resource not in CASINO_RESOURCES:
        await cb.answer("❌ Неизвестный ресурс.", show_alert=True)
        return

    label = CASINO_RESOURCES[resource]
    balance = getattr(user, resource, 0)

    await state.set_state(SlotsFSM.waiting_amount)
    await state.update_data(resource=resource)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_casino_slots"))
    await safe_edit(
        cb.message,
        f"🎰 <b>Ставка: {label}</b>\n\n"
        f"Ваш баланс: <b>{fmt_num(balance)}</b>\n\n"
        f"Введите размер ставки:",
        reply_markup=cancel_kb.as_markup(),
    )
    await cb.answer()


@router.message(SlotsFSM.waiting_amount)
async def msg_slots_bet(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    resource = data.get("resource", "nh_coins")
    await state.clear()

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_casino_slots"), parse_mode="HTML")
        return

    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.slots_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("⏳ Подождите, предыдущая ставка ещё обрабатывается.", reply_markup=back_kb("bank_casino_slots"))
        return

    result = await slots_service.play(session, user, resource, amount)

    if not result.get("ok"):
        builder = InlineKeyboardBuilder()
        if result.get("x3_warn"):
            builder.row(InlineKeyboardButton(text="🔄 Изменить ставку", callback_data=f"slots_pick:{resource}"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino_slots"))
        await message.answer(result["msg"], reply_markup=builder.as_markup(), parse_mode="HTML")
        return

    reel = result["reel"]
    outcome = result["outcome"]
    label = result["resource_label"]
    payout = result["payout"]
    new_balance = getattr(user, resource, 0)
    reel_text = slots_service.render_reel(reel)

    if outcome == "triple":
        profit = payout - amount
        text = (
            f"🎰 {reel_text} 🎰\n\n"
            f"🎉 <b>ДЖЕКПОТ!</b>\n\n"
            f"Ставка: {fmt_num(amount)} {label}\n"
            f"Выигрыш: +{fmt_num(profit)} {label}\n"
            f"Итого получено: {fmt_num(payout)} {label}\n\n"
            f"Новый баланс: {fmt_num(new_balance)} {label}"
        )
    elif outcome == "pair":
        text = (
            f"🎰 {reel_text} 🎰\n\n"
            f"🔁 <b>Возврат ставки</b>\n\n"
            f"Ставка: {fmt_num(amount)} {label} — возвращена\n\n"
            f"Баланс: {fmt_num(new_balance)} {label}"
        )
    else:
        text = (
            f"🎰 {reel_text} 🎰\n\n"
            f"😔 <b>Проигрыш!</b>\n\n"
            f"Ставка: {fmt_num(amount)} {label}\n"
            f"Потеряно: -{fmt_num(amount)} {label}\n\n"
            f"Новый баланс: {fmt_num(new_balance)} {label}"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎰 Крутить снова", callback_data=f"slots_pick:{resource}"))
    builder.row(InlineKeyboardButton(text="◀️ В казино", callback_data="bank_casino_slots"))
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
