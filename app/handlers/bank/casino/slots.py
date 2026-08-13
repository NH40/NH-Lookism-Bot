"""Слоты: выбор ресурса, ставка, прокрутка барабана."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.casino.slots_service import slots_service
from app.services.bank.casino.common import CASINO_RESOURCES, get_balance
from app.constants.bank import SLOTS_MULTIPLIERS, SLOTS_SYMBOL_EMOJI, SLOTS_SYMBOLS
from app.services.cooldown_service import cooldown_service
from app.utils.formatters import fmt_num
from app.utils.keyboards.common import back_kb
from app.utils.menu_media import safe_edit

router = Router()


class SlotsFSM(StatesGroup):
    waiting_bet = State()


# ── Вспомогательные ──────────────────────────────────────────────────────────

def _slots_main_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    for res, label in CASINO_RESOURCES.items():
        # Пропускаем статистов — они только в блэкджеке
        if res == "squad":
            continue
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"slots_pick:{res}"
        ))
    builder.row(InlineKeyboardButton(text="📊 Таблица выплат", callback_data="slots_paytable"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
    return builder.as_markup()


def _paytable_text() -> str:
    lines = ["📊 <b>Таблица выплат (слоты)</b>\n"]
    for symbol in SLOTS_SYMBOLS:
        emoji = SLOTS_SYMBOL_EMOJI[symbol]
        mult = SLOTS_MULTIPLIERS[symbol]
        lines.append(f"{emoji} {symbol} → x{mult:.1f}")
    lines.append("\n<i>Три одинаковых символа = выигрыш.</i>")
    lines.append("<i>Два одинаковых = возврат ставки.</i>")
    return "\n".join(lines)


def _paytable_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="slots_menu"))
    return builder.as_markup()


# ── Главное меню слотов ──────────────────────────────────────────────────────

@router.callback_query(F.data == "bank_casino_slots")
async def cb_slots_menu(cb: CallbackQuery):
    await safe_edit(cb, "🎰 <b>Слоты</b>\n\nВыберите ресурс для ставки:", _slots_main_kb())
    await cb.answer()


@router.callback_query(F.data == "slots_menu")
async def cb_slots_menu_back(cb: CallbackQuery):
    await safe_edit(cb, "🎰 <b>Слоты</b>\n\nВыберите ресурс для ставки:", _slots_main_kb())
    await cb.answer()


@router.callback_query(F.data == "slots_paytable")
async def cb_slots_paytable(cb: CallbackQuery):
    await safe_edit(cb, _paytable_text(), _paytable_kb())
    await cb.answer()


# ── Выбор ресурса ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("slots_pick:"))
async def cb_slots_pick(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    resource = cb.data.split(":")[1]

    if resource not in CASINO_RESOURCES:
        await cb.answer("❌ Неизвестный ресурс.", show_alert=True)
        return

    # Статистов в слотах нет
    if resource == "squad":
        await cb.answer("❌ Статисты доступны только в блэкджеке.", show_alert=True)
        return

    balance = get_balance(user, resource)
    await state.set_state(SlotsFSM.waiting_bet)
    await state.update_data(resource=resource)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="slots_menu"))

    await safe_edit(
        cb,
        f"🎰 <b>Слоты — {CASINO_RESOURCES[resource]}</b>\n\n"
        f"Баланс: {fmt_num(balance)}\n\n"
        f"Введите сумму ставки:",
        builder.as_markup()
    )
    await cb.answer()


# ── Ввод суммы ставки ────────────────────────────────────────────────────────

@router.message(SlotsFSM.waiting_bet)
async def msg_slots_bet(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    resource = data.get("resource")
    await state.clear()

    if not resource:
        await message.answer("❌ Ресурс не выбран.", reply_markup=back_kb("slots_menu"), parse_mode="HTML")
        return

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("slots_menu"), parse_mode="HTML")
        return

    if amount <= 0:
        await message.answer("❌ Ставка должна быть больше нуля.", reply_markup=back_kb("slots_menu"), parse_mode="HTML")
        return

    lock_key = cooldown_service.slots_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("⏳ Подождите, предыдущее действие ещё обрабатывается.", reply_markup=back_kb("slots_menu"))
        return
    try:
        result = await slots_service.play(session, user, resource, amount)
    finally:
        await cooldown_service.release_lock(lock_key)

    if not result.get("ok", False):
        if result.get("x3_warn"):
            await message.answer(result["msg"], reply_markup=back_kb("slots_menu"), parse_mode="HTML")
        else:
            await message.answer(result.get("msg", "❌ Ошибка."), reply_markup=back_kb("slots_menu"), parse_mode="HTML")
        return

    reel_str = slots_service.render_reel(result["reel"])
    outcome = result["outcome"]

    if outcome == "triple":
        outcome_text = "🎉 ТРИ В ОДИНАКОВЫХ! ВЫИГРЫШ!"
    elif outcome == "pair":
        outcome_text = "🔄 Два одинаковых — возврат ставки."
    else:
        outcome_text = "💔 Проигрыш."

    msg = (
        f"🎰 <b>Результат</b>\n\n"
        f"{reel_str}\n\n"
        f"{outcome_text}\n"
        f"Ставка: {fmt_num(amount)} {result['resource_label']}\n"
        f"Выигрыш: {fmt_num(result['payout'])} {result['resource_label']}"
    )

    await message.answer(msg, reply_markup=back_kb("slots_menu"), parse_mode="HTML")