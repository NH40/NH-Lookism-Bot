"""Крипто-ферма: покупка/продажа монет, просмотр курсов."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.crypto_service import (
    crypto_service, CRYPTO_CONFIG, CRYPTO_CURRENCIES, SELL_COMMISSION_PCT
)
from app.utils.formatters import fmt_num
from app.utils.keyboards.common import back_kb

router = Router()


class CryptoFSM(StatesGroup):
    waiting_buy_amount  = State()
    waiting_sell_amount = State()


# ── Меню фермы ────────────────────────────────────────────────────────────────

async def _crypto_text(session: AsyncSession, user_id: int) -> str:
    prices = await crypto_service.get_all_prices(session)
    holdings = await crypto_service.get_all_holdings(session, user_id)

    lines = ["₿ <b>Крипто-ферма</b>\n", "📊 Текущий курс (NHCoin за 1 монету):\n"]
    for cur, cfg in CRYPTO_CONFIG.items():
        price_row = prices.get(cur)
        if not price_row:
            lines.append(f"{cfg['emoji']} <b>{cur}</b> — —")
            continue

        price_disp = crypto_service.micro_to_display(price_row.price_micro)
        base = cfg["base_price"]
        deviation_pct = (price_row.price_micro - base) / base * 100
        if deviation_pct >= 1:
            trend = f" 📈+{deviation_pct:.1f}%"
        elif deviation_pct <= -1:
            trend = f" 📉{deviation_pct:.1f}%"
        else:
            trend = ""

        buy_vol  = price_row.buy_volume_micro  or 0
        sell_vol = price_row.sell_volume_micro or 0
        if buy_vol > sell_vol * 1.2:
            sentiment = " 🟢"
        elif sell_vol > buy_vol * 1.2:
            sentiment = " 🔴"
        else:
            sentiment = ""

        holding = holdings.get(cur)
        hold_str = f"\n    У вас: {holding.amount}" if holding and holding.amount > 0 else ""
        avg_str = ""
        if holding and holding.amount > 0:
            avg = crypto_service.micro_to_display(holding.avg_buy_price_micro)
            avg_str = f" (ср. покупка: {avg})"
        lines.append(f"{cfg['emoji']} <b>{cur}</b> — {price_disp} NHCoin{trend}{sentiment}{hold_str}{avg_str}")

    lines.append("\n<i>Цена формируется игроками. Тик маркет-мейкера каждые 5 мин.</i>")
    return "\n".join(lines)


def _crypto_kb(holdings: dict) -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    for cur, cfg in CRYPTO_CONFIG.items():
        builder.row(
            InlineKeyboardButton(text=f"🟢 Купить {cfg['emoji']}{cur}", callback_data=f"crypto_buy:{cur}"),
            InlineKeyboardButton(text=f"🔴 Продать", callback_data=f"crypto_sell:{cur}"),
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()


@router.callback_query(F.data == "bank_crypto")
async def cb_bank_crypto(cb: CallbackQuery, session: AsyncSession, user: User):
    await crypto_service.ensure_prices(session)
    text = await _crypto_text(session, user.id)
    holdings = await crypto_service.get_all_holdings(session, user.id)
    try:
        await cb.message.edit_text(text, reply_markup=_crypto_kb(holdings), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Купить крипту ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("crypto_buy:"))
async def cb_crypto_buy(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    currency = cb.data.split(":")[1]
    if currency not in CRYPTO_CONFIG:
        await cb.answer("❌ Неизвестная монета.", show_alert=True)
        return

    await crypto_service.ensure_prices(session)
    prices = await crypto_service.get_all_prices(session)
    price_row = prices.get(currency)
    price_micro = price_row.price_micro if price_row else CRYPTO_CONFIG[currency]["base_price"]
    price_nh = price_micro // 100

    cfg = CRYPTO_CONFIG[currency]
    await state.set_state(CryptoFSM.waiting_buy_amount)
    await state.update_data(currency=currency, price_micro=price_micro)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_crypto"))
    try:
        await cb.message.edit_text(
            f"{cfg['emoji']} <b>Купить {currency}</b>\n\n"
            f"Текущая цена: <b>{crypto_service.micro_to_display(price_micro)} NHCoin</b>\n"
            f"Ваш баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"{cfg['desc']}\n\n"
            f"Введите количество монет для покупки:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(CryptoFSM.waiting_buy_amount)
async def msg_crypto_buy(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "CriptoNH")
    await state.clear()

    try:
        units = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_crypto"), parse_mode="HTML")
        return

    ok, err, delta_pct = await crypto_service.buy(session, user, currency, units)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_crypto"), parse_mode="HTML")
        return

    prices = await crypto_service.get_all_prices(session)
    price_micro = prices[currency].price_micro
    total = (price_micro * units) // 100
    cfg = CRYPTO_CONFIG[currency]
    delta_str = f"📈 Ваша покупка подняла курс на {delta_pct:+.2f}%\n" if abs(delta_pct) >= 0.01 else ""
    await message.answer(
        f"✅ Куплено <b>{units} {cfg['emoji']}{currency}</b>\n"
        f"Потрачено: {fmt_num(total)} NHCoin\n"
        f"{delta_str}"
        f"Остаток: {fmt_num(user.nh_coins)} NHCoin",
        reply_markup=back_kb("bank_crypto"),
        parse_mode="HTML",
    )


# ── Продать крипту ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("crypto_sell:"))
async def cb_crypto_sell(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    currency = cb.data.split(":")[1]
    if currency not in CRYPTO_CONFIG:
        await cb.answer("❌ Неизвестная монета.", show_alert=True)
        return

    holding = await crypto_service.get_holding(session, user.id, currency)
    amount = holding.amount if holding else 0
    if amount <= 0:
        await cb.answer(f"❌ У вас нет {currency}.", show_alert=True)
        return

    await crypto_service.ensure_prices(session)
    prices = await crypto_service.get_all_prices(session)
    price_micro = prices[currency].price_micro if currency in prices else CRYPTO_CONFIG[currency]["base_price"]
    cfg = CRYPTO_CONFIG[currency]

    await state.set_state(CryptoFSM.waiting_sell_amount)
    await state.update_data(currency=currency, price_micro=price_micro)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(
        text=f"💰 Продать всё ({amount} монет)",
        callback_data=f"crypto_sell_all:{currency}"
    ))
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bank_crypto"))
    try:
        gross_all = (price_micro * amount) // 100
        net_all = gross_all - max(1, gross_all * SELL_COMMISSION_PCT // 100)
        await cb.message.edit_text(
            f"{cfg['emoji']} <b>Продать {currency}</b>\n\n"
            f"У вас: <b>{amount} монет</b>\n"
            f"Текущая цена: {crypto_service.micro_to_display(price_micro)} NHCoin\n"
            f"Получите (за всё): ~{fmt_num(net_all)} NHCoin\n"
            f"<i>Комиссия биржи: {SELL_COMMISSION_PCT}%</i>\n\n"
            f"Введите количество монет для продажи:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("crypto_sell_all:"))
async def cb_crypto_sell_all(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    currency = cb.data.split(":")[1]
    holding = await crypto_service.get_holding(session, user.id, currency)
    if not holding or holding.amount <= 0:
        await cb.answer("❌ Нечего продавать.", show_alert=True)
        return
    units = holding.amount
    ok, err, delta_pct, revenue = await crypto_service.sell(session, user, currency, units)
    if not ok:
        await cb.answer(err, show_alert=True)
        return

    cfg = CRYPTO_CONFIG[currency]
    delta_str = f"📉 Ваша продажа опустила курс на {delta_pct:.2f}%\n" if abs(delta_pct) >= 0.01 else ""
    try:
        await cb.message.edit_text(
            f"✅ Продано <b>{units} {cfg['emoji']}{currency}</b>\n"
            f"Получено: {fmt_num(revenue)} NHCoin\n"
            f"{delta_str}",
            reply_markup=back_kb("bank_crypto"),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(CryptoFSM.waiting_sell_amount)
async def msg_crypto_sell(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "CriptoNH")
    await state.clear()

    try:
        units = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("bank_crypto"), parse_mode="HTML")
        return

    ok, err, delta_pct, revenue = await crypto_service.sell(session, user, currency, units)
    if not ok:
        await message.answer(err, reply_markup=back_kb("bank_crypto"), parse_mode="HTML")
        return

    cfg = CRYPTO_CONFIG[currency]
    delta_str = f"📉 Ваша продажа опустила курс на {delta_pct:.2f}%\n" if abs(delta_pct) >= 0.01 else ""
    await message.answer(
        f"✅ Продано <b>{units} {cfg['emoji']}{currency}</b>\n"
        f"Получено: {fmt_num(revenue)} NHCoin\n"
        f"{delta_str}"
        f"Баланс: {fmt_num(user.nh_coins)} NHCoin",
        reply_markup=back_kb("bank_crypto"),
        parse_mode="HTML",
    )
