from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery
from app.utils.formatters import skill_path_label

router = Router()


@router.callback_query(F.data == "skills")
async def cb_skills(cb: CallbackQuery, session: AsyncSession, user: User):
    await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )

    path_emoji = {
        "businessman": "💼", "romantic": "💝", "monster": "👹"
    }.get(user.skill_path, "❓") if user.skill_path else "❓"

    ui_status = "✅ Активен" if (user.ultra_instinct or user.true_ultra_instinct or user.ui_is_donat or user.ui_level > 0) else "❌"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Мастерство",     callback_data="mastery_menu"))
    builder.row(InlineKeyboardButton(text="🗺 Путь",            callback_data="path_menu" if user.skill_path else "path_choose"))
    builder.row(InlineKeyboardButton(text="👁 Ультра Инстинкт", callback_data="ui_settings"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",           callback_data="main_menu"))

    text = (
        f"⚡ <b>Навыки</b>\n\n"
        f"💎 Очки пути: {user.skill_path_points}\n"
        f"🗺 Путь: {path_emoji} {skill_path_label(user.skill_path)}\n"
        f"👁 Ультра Инстинкт: {ui_status}\n\n"
        f"Выбери раздел:"
    )
    await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
