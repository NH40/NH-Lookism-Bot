from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.market_service import market_service
from app.constants.market import ITEM_TYPES
from app.utils.formatters import fmt_num
from app.utils.menu_media import safe_edit

router = Router()

PAGE_SIZE = 8


# ── Главное меню биржи ────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_menu")
async def cb_market_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Покупатель", callback_data="market_buyer"))
    builder.row(InlineKeyboardButton(text="💰 Продавец", callback_data="market_seller"))
    builder.row(InlineKeyboardButton(text="🔨 Аукционы", callback_data="market_auction_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    await safe_edit(
        cb,
        f"🏪 <b>Биржа</b>\n\n"
        f"💰 NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n"
        f"Выбери роль:",
        builder.as_markup(),
    )
