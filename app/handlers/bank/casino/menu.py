"""Хаб казино: слоты, блэкджек, покер, рейтинг."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.safe_edit import safe_edit

router = Router()


def casino_menu_kb() -> "InlineKeyboardMarkup":
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 Слоты",    callback_data="bank_casino_slots"),
        InlineKeyboardButton(text="🃏 Блэкджек", callback_data="bank_casino_blackjack"),
    )
    builder.row(InlineKeyboardButton(text="🂡 Покер (PvP)", callback_data="poker_menu"))
    builder.row(InlineKeyboardButton(text="🏆 Рейтинг недели", callback_data="bank_casino_rating"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="bank_menu"))
    return builder.as_markup()


@router.callback_query(F.data == "bank_casino")
async def cb_bank_casino(cb: CallbackQuery, session: AsyncSession, user: User):
    await safe_edit(
        cb.message,
        "🎰 <b>Казино</b>\n\n"
        "Испытайте удачу — слоты, блэкджек против дилера или покерный стол против других игроков.\n"
        "<i>Казино непредсказуемо — выигрыш никто не гарантирует.</i>\n\n"
        "Выберите раздел:",
        reply_markup=casino_menu_kb(),
    )
    await cb.answer()
