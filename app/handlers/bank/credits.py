"""Раздел 'Кредиты' в банке."""
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.bank import BankCredit
from app.services.bank.credits_service import (
    credits_service, MAX_CREDITS, REPAY_FACTOR, BLOCK_HOURS, DELETE_HOURS
)
from app.utils.formatters import fmt_num, fmt_ttl
from app.utils.keyboards.common import back_kb

router = Router()


class CreditFSM(StatesGroup):
    waiting_amount = State()
    waiting_repay_amount = State()


# ── Вспомогательные ──────────────────────────────────────────────────────────

def _credit_status(credit: BankCredit) -> str:
    now = datetime.now(timezone.utc)
    remaining = credit.due_amount - credit.paid_amount
    if credit.is_paid:
        return "✅ Погашен"
    if now >= credit.block_at and now < credit.delete_at:
        secs = int((credit.delete_at - now).total_seconds())
        return f"🔴 Заблокирован! До сноса банды: {fmt_ttl(secs)}"
    if now >= credit.delete_at:
        return "💀 Банда снесена"
    secs = int((credit.block_at - now).total_seconds())
    return f"🟡 Активен, до блокировки: {fmt_ttl(secs)}"


def _credits_text(credits: list[BankCredit], max_amount: int) -> str:
    lines = [
        "💳 <b>Кредиты</b>\n",
        f"Максимальная сумма: <b>{fmt_num(max_amount)} NHCoin</b>",
        f"  (Доход/час = доход/мин × 60)\n",
        f"📌 Условия:",
        f"  • Срок: {BLOCK_HOURS}ч — выплата до {int(REPAY_FACTOR*100)}% от суммы",
        f"  • Через {BLOCK_HOURS}ч блокируются действия",
        f"  • Через {DELETE_HOURS}ч банда <b>удаляется</b>",
        f"  • Кредит не обнуляется при сносе банды/престиже\n",
    ]
    if credits:
        lines.append(f"📋 Активных: {len(credits)}/{MAX_CREDITS}\n")
        for i, c in enumerate(credits, 1):
            remaining = c.due_amount - c.paid_amount
            lines.append(
                f"<b>#{i}</b> — {fmt_num(c.amount)} NHCoin\n"
                f"   К выплате: {fmt_num(remaining)} NHCoin\n"
                f"   Статус: {_credit_status(c)}"
            )
    else:
        lines.append("✅ Активных кредитов нет.")
    return "\n".join(lines)


def _credits_kb(credits: list[BankCredit], can_take: bool) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    if can_take:
        builder.row(InlineKeyboardButton(text="➕ Взять кредит", callback_data="credit_take"))
    for c in credits:
        if not c.is_paid:
            remaining = c.due_amount - c.paid_amount
            builder.row(InlineKeyboardButton(
                text=f"💸 Выплатить #{c.id} ({fmt_num(remaining)} NHCoin)",
                callback_data=f"credit_repay:{c.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()


# ── Хендлеры ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bank_credits")
async def cb_bank_credits(cb: CallbackQuery, session: AsyncSession, user: User):
    credits = await credits_service.get_active_credits(session, user.id)
    max_amount = user.income_per_minute * 60
    can_take = len(credits) < MAX_CREDITS
    try:
        await cb.message.edit_text(
            _credits_text(credits, max_amount),
            reply_markup=_credits_kb(credits, can_take),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Взять кредит ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "credit_take")
async def cb_credit_take(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    max_amount = user.income_per_minute * 60
    if max_amount <= 0:
        await cb.answer("❌ Нет дохода для получения кредита.", show_alert=True)
        return

    active = await credits_service.get_active_credits(session, user.id)
    if len(active) >= MAX_CREDITS:
        await cb.answer(f"❌ Максимум {MAX_CREDITS} кредита.", show_alert=True)
        return

    await state.set_state(CreditFSM.waiting_amount)
    await state.update_data(max_amount=max_amount)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_credits"))
    try:
        await cb.message.edit_text(
            f"💳 <b>Взять кредит</b>\n\n"
            f"Максимум: <b>{fmt_num(max_amount)} NHCoin</b>\n"
            f"К выплате: <b>{int(REPAY_FACTOR*100)}%</b> от суммы\n\n"
            f"Введите сумму кредита:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(CreditFSM.waiting_amount)
async def msg_credit_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    ok, err = await credits_service.take_credit(session, user, amount)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    due = int(amount * REPAY_FACTOR)
    await message.answer(
        f"✅ <b>Кредит выдан!</b>\n\n"
        f"Сумма: {fmt_num(amount)} NHCoin зачислены на счёт\n"
        f"К выплате: {fmt_num(due)} NHCoin\n"
        f"⏰ Срок: {BLOCK_HOURS} часа (до блокировки)\n"
        f"💀 Снос банды через: {DELETE_HOURS} часов\n\n"
        f"<i>Кредит сохранится даже после сноса банды и престижа!</i>",
        reply_markup=back_kb("bank_credits"),
        parse_mode="HTML",
    )


# ── Погасить кредит ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("credit_repay:"))
async def cb_credit_repay(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    credit_id = int(cb.data.split(":")[1])
    await state.set_state(CreditFSM.waiting_repay_amount)
    await state.update_data(credit_id=credit_id)

    # Найдём кредит для отображения суммы
    from sqlalchemy import select
    r = await session.execute(
        select(BankCredit).where(BankCredit.id == credit_id, BankCredit.user_id == user.id)
    )
    credit = r.scalar_one_or_none()
    if not credit:
        await cb.answer("❌ Кредит не найден.", show_alert=True)
        return

    remaining = credit.due_amount - credit.paid_amount
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(
        text=f"💸 Погасить полностью ({fmt_num(remaining)} NHCoin)",
        callback_data=f"credit_repay_full:{credit_id}"
    ))
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_credits"))

    try:
        await cb.message.edit_text(
            f"💸 <b>Погашение кредита #{credit_id}</b>\n\n"
            f"Осталось выплатить: <b>{fmt_num(remaining)} NHCoin</b>\n"
            f"Ваш баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"Введите сумму для частичной выплаты\nили нажмите кнопку ниже:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("credit_repay_full:"))
async def cb_credit_repay_full(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    credit_id = int(cb.data.split(":")[1])
    from sqlalchemy import select
    r = await session.execute(
        select(BankCredit).where(BankCredit.id == credit_id, BankCredit.user_id == user.id)
    )
    credit = r.scalar_one_or_none()
    if not credit:
        await cb.answer("❌ Кредит не найден.", show_alert=True)
        return
    remaining = credit.due_amount - credit.paid_amount
    ok, err = await credits_service.repay_credit(session, user, credit_id, remaining)
    if not ok:
        try:
            await cb.message.edit_text(err, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        except Exception:
            pass
        return
    try:
        await cb.message.edit_text(
            f"✅ <b>Кредит #{credit_id} полностью погашен!</b>\n\n"
            f"Выплачено: {fmt_num(remaining)} NHCoin",
            reply_markup=back_kb("bank_credits"),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(CreditFSM.waiting_repay_amount)
async def msg_repay_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    credit_id = data.get("credit_id")
    await state.clear()
    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    ok, err = await credits_service.repay_credit(session, user, credit_id, amount)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    await message.answer(
        f"✅ Выплачено <b>{fmt_num(amount)} NHCoin</b> по кредиту #{credit_id}.",
        reply_markup=back_kb("bank_credits"),
        parse_mode="HTML",
    )
