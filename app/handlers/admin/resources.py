"""Меню раздела ресурсов (входная точка → fragments.py и give_items.py)."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from app.models.user import User
from app.handlers.admin._common import is_admin

router = Router()


@router.callback_query(F.data.startswith("adm_resources:"))
async def cb_adm_resources(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = cb.data.split(":")[1]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Очки мастерства",     callback_data=f"adm_mastery:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔷 Очки пути",           callback_data=f"adm_pathpts:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔮 Фрагменты УИ",        callback_data=f"adm_uifrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🧪 Фрагменты алхимии",   callback_data=f"adm_alchfrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔷 Фрагменты Пути",      callback_data=f"adm_pathfrag:{tg_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",               callback_data=f"adm_user:{tg_id}"))
    try:
        await cb.message.edit_text("📦 Выберите ресурс для выдачи:", reply_markup=builder.as_markup())
    except Exception:
        pass
