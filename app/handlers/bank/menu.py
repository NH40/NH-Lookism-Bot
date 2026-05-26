"""Главное меню Банка."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.bank.credits_service import credits_service
from app.services.bank.investments_service import investments_service, DURATION_OPTIONS
from app.utils.formatters import fmt_num

router = Router()


async def _bank_menu_text(session: AsyncSession, user: User) -> str:
    active_credits = await credits_service.get_active_credits(session, user.id)
    active_inv = await investments_service.get_active(session, user.id)
    blocked = await credits_service.is_blocked(session, user.id)

    blocked_str = "\n⚠️ <b>Действия заблокированы!</b> Выплатите кредит!" if blocked else ""
    credit_str = f"Активных кредитов: {len(active_credits)}/3" if active_credits else "Кредитов нет"
    inv_str = f"Активных вкладов: {len(active_inv)}/3" if active_inv else "Вкладов нет"

    return (
        f"🏦 <b>Банк</b>{blocked_str}\n\n"
        f"💳 {credit_str}\n"
        f"📈 {inv_str}\n"
        f"💰 Баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
        f"Выбери раздел:"
    )


def bank_menu_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Кредиты",    callback_data="bank_credits"),
        InlineKeyboardButton(text="🎰 Казино",     callback_data="bank_casino"),
    )
    builder.row(
        InlineKeyboardButton(text="₿ Крипто-ферма", callback_data="bank_crypto"),
        InlineKeyboardButton(text="🗄 Хранилище",   callback_data="bank_storage"),
    )
    builder.row(
        InlineKeyboardButton(text="📈 Инвестиции",  callback_data="bank_investments"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


@router.callback_query(F.data == "bank_menu")
async def cb_bank_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    text = await _bank_menu_text(session, user)
    try:
        await cb.message.edit_text(text, reply_markup=bank_menu_kb(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()
