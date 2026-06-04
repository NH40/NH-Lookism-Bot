"""Инвестиции: создание вкладов, просмотр и вывод."""
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.bank import Investment
from app.services.bank.investments_service import (
    investments_service, DURATION_OPTIONS, MAX_INVESTMENTS, MAX_DEPOSIT
)
from app.utils.formatters import fmt_num, fmt_ttl
from app.utils.keyboards.common import back_kb

router = Router()


class InvestFSM(StatesGroup):
    waiting_amount = State()


# ── Вспомогательные ──────────────────────────────────────────────────────────

def _inv_status(inv: Investment) -> str:
    if inv.is_withdrawn:
        return "✅ Получен"
    now = datetime.now(timezone.utc)
    if now >= inv.matures_at:
        return "🟢 Готов к выводу!"
    remaining = int((inv.matures_at - now).total_seconds())
    return f"⏳ {fmt_ttl(remaining)}"


def _investments_text(active: list[Investment], user_balance: int) -> str:
    lines = [
        "📈 <b>Инвестиции</b>\n",
        "Открывайте вклады и получайте проценты!\n",
        "📌 Условия:",
        "  1ч → +3%  |  3ч → +5%",
        "  6ч → +10% |  12ч → +15%",
        "  24ч → +20%",
        f"  Максимум: {fmt_num(MAX_DEPOSIT)} NHCoin\n",
        f"💰 Ваш баланс: {fmt_num(user_balance)} NHCoin",
        f"📋 Активных: {len(active)}/{MAX_INVESTMENTS}\n",
    ]
    if active:
        for i, inv in enumerate(active, 1):
            payout = inv.amount + int(inv.amount * inv.interest_pct / 100)
            lines.append(
                f"<b>Вклад #{i}</b>\n"
                f"  Сумма: {fmt_num(inv.amount)} NHCoin\n"
                f"  Срок: {inv.duration_hours}ч (+{inv.interest_pct}%)\n"
                f"  Выплата: {fmt_num(payout)} NHCoin\n"
                f"  Статус: {_inv_status(inv)}"
            )
    else:
        lines.append("Вкладов нет.")
    return "\n".join(lines)


def _investments_kb(active: list[Investment], can_create: bool) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    if can_create:
        builder.row(InlineKeyboardButton(text="➕ Открыть вклад", callback_data="invest_choose_duration"))
    for inv in active:
        now = datetime.now(timezone.utc)
        if now >= inv.matures_at and not inv.is_withdrawn:
            payout = inv.amount + int(inv.amount * inv.interest_pct / 100)
            builder.row(InlineKeyboardButton(
                text=f"💰 Получить {fmt_num(payout)} NHCoin (вклад #{inv.id})",
                callback_data=f"invest_withdraw:{inv.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()


# ── Главное меню вкладов ──────────────────────────────────────────────────────

@router.callback_query(F.data == "bank_investments")
async def cb_bank_investments(cb: CallbackQuery, session: AsyncSession, user: User):
    active = await investments_service.get_active(session, user.id)
    can_create = len(active) < MAX_INVESTMENTS
    try:
        await cb.message.edit_text(
            _investments_text(active, user.nh_coins),
            reply_markup=_investments_kb(active, can_create),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Выбрать срок ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "invest_choose_duration")
async def cb_invest_choose_duration(cb: CallbackQuery, session: AsyncSession, user: User):
    active = await investments_service.get_active(session, user.id)
    if len(active) >= MAX_INVESTMENTS:
        await cb.answer(f"❌ Максимум {MAX_INVESTMENTS} вклада.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for hours, pct in DURATION_OPTIONS.items():
        builder.row(InlineKeyboardButton(
            text=f"⏱ {hours}ч → +{pct}%",
            callback_data=f"invest_pick_dur:{hours}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_investments"))
    try:
        await cb.message.edit_text(
            "📈 <b>Выберите срок вклада</b>\n\n"
            "Чем дольше срок — тем выше процент!",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("invest_pick_dur:"))
async def cb_invest_pick_dur(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    hours = int(cb.data.split(":")[1])
    if hours not in DURATION_OPTIONS:
        await cb.answer("❌ Неверный срок.", show_alert=True)
        return

    pct = DURATION_OPTIONS[hours]
    await state.set_state(InvestFSM.waiting_amount)
    await state.update_data(duration_hours=hours, interest_pct=pct)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_investments"))
    try:
        await cb.message.edit_text(
            f"📈 <b>Вклад на {hours}ч (+{pct}%)</b>\n\n"
            f"Максимум: {fmt_num(MAX_DEPOSIT)} NHCoin\n"
            f"Ваш баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"Введите сумму вклада:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(InvestFSM.waiting_amount)
async def msg_invest_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    hours = data.get("duration_hours", 1)
    pct = data.get("interest_pct", 3)
    await state.clear()

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    # Redis-лок: предотвращает параллельное создание вклада.
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.invest_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await message.answer("⏳ Подождите, предыдущий запрос ещё обрабатывается.",
                             reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    ok, err = await investments_service.create(session, user, amount, hours)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    from app.utils.region_activity import record
    await record(session, user.id, "bank")

    payout = amount + int(amount * pct / 100)
    await message.answer(
        f"✅ <b>Вклад открыт!</b>\n\n"
        f"Сумма: {fmt_num(amount)} NHCoin\n"
        f"Срок: {hours} ч\n"
        f"Выплата через {hours}ч: <b>{fmt_num(payout)} NHCoin</b> (+{pct}%)\n\n"
        f"<i>Деньги заморожены до истечения срока.</i>",
        reply_markup=back_kb("bank_investments"),
        parse_mode="HTML",
    )


# ── Вывести вклад ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("invest_withdraw:"))
async def cb_invest_withdraw(cb: CallbackQuery, session: AsyncSession, user: User):
    inv_id = int(cb.data.split(":")[1])

    # Redis-лок по ID вклада: предотвращает двойной вывод.
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.invest_withdraw_lock_key(inv_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    ok, err, payout = await investments_service.withdraw(session, user, inv_id)
    if not ok:
        try:
            await cb.message.edit_text(err, reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        except Exception:
            await cb.answer(err, show_alert=True)
        return
    try:
        await cb.message.edit_text(
            f"✅ <b>Вклад получен!</b>\n\n"
            f"Зачислено: <b>{fmt_num(payout)} NHCoin</b>\n"
            f"Баланс: {fmt_num(user.nh_coins)} NHCoin",
            reply_markup=back_kb("bank_investments"),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()
