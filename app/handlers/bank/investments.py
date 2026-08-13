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
    investments_service, MAX_INVESTMENTS, MAX_DEPOSIT, INVEST_RESOURCES, get_interest_pct
)
from app.constants.bank import INVEST_DURATION_OPTIONS, INVEST_DURATION_OPTIONS_OLD
from app.services.bank.casino.common import CASINO_RESOURCES, get_balance
from app.services.cooldown_service import cooldown_service
from app.utils.formatters import fmt_num, fmt_ttl
from app.utils.keyboards.common import back_kb
from app.utils.menu_media import safe_edit

router = Router()

class InvestFSM(StatesGroup):
    waiting_resource = State()
    waiting_duration = State()
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

def _investments_text(active: list[Investment], user: User) -> str:
    lines = [
        "📈 <b>Инвестиции</b>\n",
        "Открывайте вклады и получайте проценты!\n",
        "📌 Условия:",
    ]
    
    lines.append("  <b>Для NHCoin:</b>")
    for hours, pct in INVEST_DURATION_OPTIONS.items():
        lines.append(f"    {hours}ч → +{pct:.0f}%")
    
    lines.append("  <b>Для остальных ресурсов:</b>")
    for hours, pct in INVEST_DURATION_OPTIONS_OLD.items():
        lines.append(f"    {hours}ч → +{pct:.0f}%")
    
    lines.append(f"  Максимум: {fmt_num(MAX_DEPOSIT)} единиц ресурса")
    lines.append(f"  Максимум вкладов: {MAX_INVESTMENTS}\n")

    if active:
        lines.append("📋 <b>Ваши вклады:</b>")
        for i, inv in enumerate(active, 1):
            label = CASINO_RESOURCES.get(inv.resource, inv.resource)
            real_pct = inv.interest_pct / 10
            payout = int(inv.amount * (1 + real_pct / 100))
            lines.append(
                f"<b>#{i}</b> — {label}: {fmt_num(inv.amount)} → "
                f"{fmt_num(payout)} (+{real_pct:.1f}%) — {_inv_status(inv)}"
            )
    else:
        lines.append("Вкладов нет.")
    return "\n".join(lines)

def _investments_kb(active: list[Investment], can_create: bool):
    builder = InlineKeyboardBuilder()
    if can_create:
        builder.row(InlineKeyboardButton(text="➕ Открыть вклад", callback_data="invest_choose_resource"))
    
    # Показываем только созревшие вклады для вывода
    now = datetime.now(timezone.utc)
    for inv in active:
        if now >= inv.matures_at and not inv.is_withdrawn:
            label = CASINO_RESOURCES.get(inv.resource, inv.resource)
            real_pct = inv.interest_pct / 10
            payout = int(inv.amount * (1 + real_pct / 100))
            builder.row(InlineKeyboardButton(
                text=f"💰 Получить {fmt_num(payout)} {label} (вклад #{inv.id})",
                callback_data=f"invest_withdraw:{inv.id}"
            ))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()

# ── Главное меню ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "bank_investments")
async def cb_bank_investments(cb: CallbackQuery, session: AsyncSession, user: User):
    active = await investments_service.get_all_investments(session, user.id)
    can_create = len([i for i in active if not i.is_withdrawn and datetime.now(timezone.utc) < i.matures_at]) < MAX_INVESTMENTS
    await safe_edit(cb, _investments_text(active, user), _investments_kb(active, can_create))
    await cb.answer()

# ── Выбор ресурса ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "invest_choose_resource")
async def cb_invest_choose_resource(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    active = await investments_service.get_active(session, user.id)
    if len(active) >= MAX_INVESTMENTS:
        await cb.answer(f"❌ Максимум {MAX_INVESTMENTS} вклада.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for res, label in INVEST_RESOURCES.items():
        balance = get_balance(user, res)
        builder.row(InlineKeyboardButton(
            text=f"{label} (баланс: {fmt_num(balance)})",
            callback_data=f"invest_pick_res:{res}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_investments"))

    await safe_edit(
        cb,
        "📈 <b>Выберите ресурс для вклада</b>\n\n"
        "Вы можете вложить любой ресурс (кроме статистов).",
        builder.as_markup()
    )
    await cb.answer()

@router.callback_query(F.data.startswith("invest_pick_res:"))
async def cb_invest_pick_res(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    resource = cb.data.split(":")[1]
    if resource not in INVEST_RESOURCES:
        await cb.answer("❌ Недопустимый ресурс.", show_alert=True)
        return
    await state.update_data(resource=resource)
    await state.set_state(InvestFSM.waiting_duration)

    builder = InlineKeyboardBuilder()
    if resource == "nh_coins":
        options = INVEST_DURATION_OPTIONS
    else:
        options = INVEST_DURATION_OPTIONS_OLD
    
    for hours, pct in options.items():
        builder.row(InlineKeyboardButton(
            text=f"⏱ {hours}ч → +{pct:.1f}%",
            callback_data=f"invest_pick_dur:{hours}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_investments"))
    
    label = INVEST_RESOURCES[resource]
    await safe_edit(
        cb,
        f"📈 <b>Вклад в {label}</b>\n\n"
        f"{'NHCoin' if resource == 'nh_coins' else 'Остальные ресурсы'}: "
        f"{'полные' if resource == 'nh_coins' else 'уменьшенные'} проценты\n\n"
        f"Выберите срок:",
        builder.as_markup()
    )
    await cb.answer()

@router.callback_query(F.data.startswith("invest_pick_dur:"))
async def cb_invest_pick_dur(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    hours = int(cb.data.split(":")[1])
    
    data = await state.get_data()
    resource = data.get("resource")
    if not resource:
        await cb.answer("❌ Ресурс не выбран.", show_alert=True)
        return

    # Проверяем, что часы есть в словаре
    if resource == "nh_coins":
        if hours not in INVEST_DURATION_OPTIONS:
            await cb.answer("❌ Неверный срок.", show_alert=True)
            return
    else:
        if hours not in INVEST_DURATION_OPTIONS_OLD:
            await cb.answer("❌ Неверный срок.", show_alert=True)
            return

    await state.update_data(duration_hours=hours)
    await state.set_state(InvestFSM.waiting_amount)

    pct = get_interest_pct(resource, hours)
    balance = get_balance(user, resource)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_investments"))

    await safe_edit(
        cb,
        f"📈 <b>Вклад на {hours}ч (+{pct:.1f}%)</b>\n\n"
        f"Ресурс: {INVEST_RESOURCES[resource]}\n"
        f"Доступно: {fmt_num(balance)}\n"
        f"Максимум: {fmt_num(MAX_DEPOSIT)}\n\n"
        f"Введите сумму вклада:",
        cancel_kb.as_markup()
    )
    await cb.answer()

@router.message(InvestFSM.waiting_amount)
async def msg_invest_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    resource = data.get("resource")
    hours = data.get("duration_hours")
    await state.clear()

    if not resource or not hours:
        await message.answer("❌ Ошибка выбора. Начните заново.", reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше нуля.", reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    lock_key = cooldown_service.invest_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await message.answer("⏳ Подождите, предыдущее действие ещё обрабатывается.", reply_markup=back_kb("bank_investments"))
        return
    try:
        ok, err = await investments_service.create(session, user, resource, amount, hours)
    finally:
        await cooldown_service.release_lock(lock_key)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_investments"), parse_mode="HTML")
        return

    from app.utils.region_activity import record
    await record(session, user.id, "bank")

    pct = get_interest_pct(resource, hours)
    payout = int(amount * (1 + pct / 100))
    await message.answer(
        f"✅ <b>Вклад открыт!</b>\n\n"
        f"Ресурс: {INVEST_RESOURCES[resource]}\n"
        f"Сумма: {fmt_num(amount)}\n"
        f"Срок: {hours} ч\n"
        f"Выплата через {hours}ч: <b>{fmt_num(payout)} {INVEST_RESOURCES[resource]}</b> (+{pct:.1f}%)\n\n"
        f"<i>Ресурс заморожен до истечения срока.</i>",
        reply_markup=back_kb("bank_investments"),
        parse_mode="HTML",
    )

# ── ВЫВОД ВКЛАДА (ИСПРАВЛЕННЫЙ) ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("invest_withdraw:"))
async def cb_invest_withdraw(cb: CallbackQuery, session: AsyncSession, user: User):
    """Забрать награду с инвестиций."""
    inv_id = int(cb.data.split(":")[1])

    lock_key = cooldown_service.invest_withdraw_lock_key(inv_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Подождите, предыдущее действие ещё обрабатывается.", show_alert=True)
        return
    try:
        ok, err, payout = await investments_service.withdraw(session, user, inv_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)
    
    if not ok:
        await cb.answer(err, show_alert=True)
        return

    inv = await session.get(Investment, inv_id)
    label = CASINO_RESOURCES.get(inv.resource, inv.resource) if inv else "ресурс"
    
    # Обновляем меню
    active = await investments_service.get_all_investments(session, user.id)
    can_create = len([i for i in active if not i.is_withdrawn and datetime.now(timezone.utc) < i.matures_at]) < MAX_INVESTMENTS
    
    await safe_edit(
        cb,
        _investments_text(active, user),
        _investments_kb(active, can_create)
    )
    
    # Отдельное уведомление о получении
    await cb.answer(f"✅ Получено {fmt_num(payout)} {label}!", show_alert=True)