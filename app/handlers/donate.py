"""
Система пополнения NHDonate через YooKassa (Telegram Payments).

Поток:
  /donate  →  меню (баланс + опции)
  → "Пополнить"  →  выбор суммы / ввод вручную
  → бот отправляет invoice  →  пользователь платит
  → pre_checkout_query  →  ответ ok
  → successful_payment  →  зачисляется nh_donate, пишется история
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.config import settings
from app.utils.formatters import fmt_num

router = Router()

MIN_DONATE = 50    # минимальная сумма в рублях
MAX_DONATE = 50000  # максимальная сумма в рублях


class DonateFSM(StatesGroup):
    waiting_amount = State()


# ── Главное меню доната ──────────────────────────────────────────────────────

async def _show_donate_menu(target: Message, user: User, edit: bool = False) -> None:
    """Отрисовывает главное меню доната (nh_donate баланс + кнопки)."""
    nh_donate = user.nh_donate or 0

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💳 Пополнить NHDonate",
        callback_data="donate_topup",
    ))
    builder.row(
        InlineKeyboardButton(text="💎 Донатные титулы", callback_data="donat_sets_menu"),
        InlineKeyboardButton(text="🔄 Чёрный рынок",   callback_data="black_market"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    text = (
        f"💎 <b>Донат-магазин</b>\n\n"
        f"🪙 Баланс NHDonate: <b>{fmt_num(nh_donate)}</b>\n"
        f"<i>1 NHDonate = 1 ₽</i>\n\n"
        f"<b>На что тратить NHDonate:</b>\n"
        f"• 💎 Донатные титулы — покупаются по одному\n"
        f"• 🔄 Круговые донаты — покупаются по кругу\n\n"
        f"Нажмите <b>«Пополнить»</b>, чтобы купить NHDonate."
    )

    if edit:
        try:
            await target.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
    else:
        await target.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(Command("donate"))
async def cmd_donate(message: Message, user: User) -> None:
    await _show_donate_menu(message, user, edit=False)


@router.callback_query(F.data == "donate_menu")
async def cb_donate_menu(cb: CallbackQuery, user: User) -> None:
    await _show_donate_menu(cb.message, user, edit=True)
    await cb.answer()


# ── Пополнение: выбор суммы ──────────────────────────────────────────────────

@router.callback_query(F.data == "donate_topup")
async def cb_donate_topup(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DonateFSM.waiting_amount)

    builder = InlineKeyboardBuilder()
    for amt in [50, 100, 200, 500, 1000, 2000]:
        builder.button(text=f"{amt} ₽", callback_data=f"donate_quick:{amt}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="donate_menu"))

    try:
        await cb.message.edit_text(
            f"💳 <b>Пополнение NHDonate</b>\n\n"
            f"Выберите сумму или введите своё число:\n"
            f"<i>Мин. {MIN_DONATE} ₽ · Макс. {MAX_DONATE} ₽ · 1 ₽ = 1 NHDonate</i>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("donate_quick:"))
async def cb_donate_quick(cb: CallbackQuery, bot: Bot, user: User, state: FSMContext) -> None:
    await state.clear()
    amount = int(cb.data.split(":")[1])
    await _send_invoice(cb.message, bot, user, amount)
    await cb.answer()


@router.message(DonateFSM.waiting_amount)
async def msg_donate_amount(message: Message, bot: Bot, user: User, state: FSMContext) -> None:
    await state.clear()
    try:
        amount = int(message.text.strip())
        if not (MIN_DONATE <= amount <= MAX_DONATE):
            raise ValueError
    except (ValueError, AttributeError):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="donate_topup"))
        await message.answer(
            f"❌ Введите целое число от <b>{MIN_DONATE}</b> до <b>{MAX_DONATE}</b> рублей.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return
    await _send_invoice(message, bot, user, amount)


# ── Отправка счёта ───────────────────────────────────────────────────────────

async def _send_invoice(target: Message, bot: Bot, user: User, amount: int) -> None:
    """Отправляет Telegram-счёт через YooKassa."""
    if not settings.YOOKASSA_PAYMENT_TOKEN:
        await target.answer(
            "❌ Платёжная система временно недоступна. Попробуйте позже.",
            parse_mode="HTML",
        )
        return

    try:
        await bot.send_invoice(
            chat_id=user.tg_id,
            title="Пополнение NHDonate",
            description=f"Вы получите {amount} NHDonate для покупки донатных привилегий в NH Lookism Bot",
            payload=f"nh_donate:{user.tg_id}:{amount}",
            provider_token=settings.YOOKASSA_PAYMENT_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=f"{amount} NHDonate", amount=amount * 100)],
            start_parameter="donate",
            protect_content=False,
        )
    except Exception as e:
        await target.answer(
            f"❌ Ошибка создания счёта. Попробуйте позже.\n<code>{e}</code>",
            parse_mode="HTML",
        )


# ── Подтверждение предоплаты ─────────────────────────────────────────────────

@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout: PreCheckoutQuery, bot: Bot) -> None:
    """Подтверждаем оплату. Должен ответить в течение 10 секунд."""
    if not pre_checkout.invoice_payload.startswith("nh_donate:"):
        await bot.answer_pre_checkout_query(
            pre_checkout.id,
            ok=False,
            error_message="Неверный платёж. Обратитесь к администратору.",
        )
        return
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


# ── Успешная оплата ──────────────────────────────────────────────────────────

@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message, session: AsyncSession, user: User
) -> None:
    """Зачисляет NHDonate и сохраняет историю платежа."""
    sp = message.successful_payment
    amount_rub = sp.total_amount // 100  # kopecks → rubles

    # Проверяем payload
    if not sp.invoice_payload.startswith("nh_donate:"):
        return

    # Зачисляем NHDonate
    user.nh_donate = (user.nh_donate or 0) + amount_rub

    # Пишем историю через ORM (таблица создаётся автоматически при старте)
    from app.models.payment import Payment
    record = Payment(
        user_id=user.id,
        tg_payment_charge_id=sp.telegram_payment_charge_id,
        provider_payment_charge_id=sp.provider_payment_charge_id,
        amount_rub=amount_rub,
        nh_donate_credited=amount_rub,
        payload=sp.invoice_payload,
        status="success",
    )
    session.add(record)
    await session.commit()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💎 Купить донатные титулы", callback_data="donat_sets_menu"
    ))
    builder.row(InlineKeyboardButton(
        text="🔄 Чёрный рынок (круговые донаты)", callback_data="black_market"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ К донат-меню", callback_data="donate_menu"
    ))

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"💰 Зачислено: <b>+{fmt_num(amount_rub)} NHDonate</b>\n"
        f"🪙 Текущий баланс: <b>{fmt_num(user.nh_donate)} NHDonate</b>\n\n"
        f"Используйте NHDonate для покупки донатных привилегий!",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
