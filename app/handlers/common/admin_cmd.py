from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

router = Router()


# ── /admin ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, user: User):
    from app.config import settings
    if message.from_user.id not in settings.admin_ids_list:
        return
    from app.utils.keyboards.admin import admin_main_kb
    await message.answer(
        "🔧 <b>Панель администратора</b>",
        reply_markup=admin_main_kb(),
        parse_mode="HTML",
    )
