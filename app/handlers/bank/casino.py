"""Казино: ставки на ресурсы с детектором x3."""
import html

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.casino_service import casino_service, CASINO_RESOURCES, WIN_CHANCE
from app.utils.formatters import fmt_num
from app.utils.keyboards.common import back_kb

router = Router()


class CasinoFSM(StatesGroup):
    waiting_resource = State()
    waiting_amount   = State()


# ── Главное меню казино ───────────────────────────────────────────────────────

def _casino_main_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    for res, label in CASINO_RESOURCES.items():
        builder.row(InlineKeyboardButton(
            text=f"🎲 Поставить {label}",
            callback_data=f"casino_pick:{res}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()


@router.callback_query(F.data == "bank_casino")
async def cb_bank_casino(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        await cb.message.edit_text(
            "🎰 <b>Казино</b>\n\n"
            "Поставьте ресурс и испытайте удачу!\n"
            "<i>Казино непредсказуемо — выигрыш никто не гарантирует.</i>\n\n"
            "Выберите ресурс для ставки:",
            reply_markup=_casino_main_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Выбрать ресурс → ввести ставку ────────────────────────────────────────────

@router.callback_query(F.data.startswith("casino_pick:"))
async def cb_casino_pick(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    resource = cb.data.split(":")[1]
    if resource not in CASINO_RESOURCES:
        await cb.answer("❌ Неизвестный ресурс.", show_alert=True)
        return

    label = CASINO_RESOURCES[resource]
    balance = casino_service.get_balance(user, resource)

    await state.set_state(CasinoFSM.waiting_amount)
    await state.update_data(resource=resource)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_casino"))
    try:
        await cb.message.edit_text(
            f"🎲 <b>Ставка: {label}</b>\n\n"
            f"Ваш баланс: <b>{fmt_num(balance)}</b>\n\n"
            f"Введите размер ставки:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Обработка ставки ──────────────────────────────────────────────────────────

@router.message(CasinoFSM.waiting_amount)
async def msg_casino_bet(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    resource = data.get("resource", "nh_coins")
    await state.clear()

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer(
            "❌ Введите целое число.",
            reply_markup=back_kb("bank_casino"),
            parse_mode="HTML",
        )
        return

    # Redis-лок: предотвращает параллельные ставки с одного аккаунта
    # (пользователь может отправить несколько сообщений очень быстро)
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.casino_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer(
            "⏳ Подождите, предыдущая ставка ещё обрабатывается.",
            reply_markup=back_kb("bank_casino"),
        )
        return

    result = await casino_service.place_bet(session, user, resource, amount)

    if not result.get("ok"):
        if result.get("x3_warn"):
            # Предупреждение о x3 стратегии
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(
                text="🔄 Изменить ставку", callback_data=f"casino_pick:{resource}"
            ))
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_casino"))
            await message.answer(
                result["msg"],
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                result["msg"],
                reply_markup=back_kb("bank_casino"),
                parse_mode="HTML",
            )
        return

    # Результат
    win = result["win"]
    label = result["resource_label"]
    payout = result["payout"]
    new_balance = casino_service.get_balance(user, resource)

    if win:
        profit = payout - amount
        text = (
            f"🎉 <b>ПОБЕДА!</b>\n\n"
            f"Ставка: {fmt_num(amount)} {label}\n"
            f"Выигрыш: +{fmt_num(profit)} {label}\n"
            f"Итого получено: {fmt_num(payout)} {label}\n\n"
            f"Новый баланс: {fmt_num(new_balance)} {label}"
        )
    else:
        text = (
            f"😔 <b>Проигрыш!</b>\n\n"
            f"Ставка: {fmt_num(amount)} {label}\n"
            f"Потеряно: -{fmt_num(amount)} {label}\n\n"
            f"Новый баланс: {fmt_num(new_balance)} {label}\n\n"
            f"<i>Удача переменчива. Попробуйте снова!</i>"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🎲 Поставить снова", callback_data=f"casino_pick:{resource}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ В казино", callback_data="bank_casino"))
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
