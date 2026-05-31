from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.market_service import market_service
from app.constants.market import ITEM_TYPES
from app.utils.formatters import fmt_num

router = Router()

PAGE_SIZE = 8


# ── Главное меню биржи ────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_menu")
async def cb_market_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Покупатель", callback_data="market_buyer"))
    builder.row(InlineKeyboardButton(text="💰 Продавец", callback_data="market_seller"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    try:
        await cb.message.edit_text(
            f"🏪 <b>Биржа</b>\n\n"
            f"💰 NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n"
            f"🏢 Фрагм. бизнеса: <b>{user.business_fragments}</b>\n"
            f"⚔️ Очки войны: <b>{user.war_points}</b>\n\n"
            f"Выбери роль:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
