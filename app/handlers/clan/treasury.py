import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.clan import clan_service
from app.utils.formatters import fmt_num

router = Router()


class TreasuryFSM(StatesGroup):
    waiting_amount = State()


@router.callback_query(F.data == "clan_treasury")
async def cb_clan_treasury(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Пополнить NHCoin", callback_data="clan_treasury_deposit_coin"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    text = (
        f"🏦 <b>Казна клана {html.escape(clan.name)}</b>\n\n"
        f"💰 NHCoin: <b>{fmt_num(clan.treasury)}</b>   (у вас: {fmt_num(user.nh_coins)})\n\n"
        f"Что хотите сделать?"
    )
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "clan_treasury_deposit_coin")
async def cb_clan_treasury_deposit_coin(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    await state.set_state(TreasuryFSM.waiting_amount)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_treasury"))

    try:
        await cb.message.edit_text(
            f"🏦 <b>Казна клана {html.escape(clan.name)}</b>\n\n"
            f"В казне: {fmt_num(clan.treasury)} NHCoin\n"
            f"У вас: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"Введите сумму для пополнения:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(TreasuryFSM.waiting_amount)
async def msg_treasury_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    from app.services.cooldown_service import cooldown_service
    await state.clear()

    lock_key = cooldown_service.treasury_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("❌ Подожди...")
        return

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.deposit_treasury(session, clan, user, amount)
    if result["ok"]:
        cashback = result.get("cashback", 0)
        cashback_pct = result.get("cashback_pct", 0)
        text = (
            f"✅ Вы пополнили казну на <b>{fmt_num(amount)} NHCoin</b>!\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin"
        )
        if cashback > 0:
            text += f"\n\n💸 <b>Кешбэк!</b> +{fmt_num(cashback)} NHCoin ({cashback_pct}%) вернулось вам!"
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(f"❌ {result['reason']}")
