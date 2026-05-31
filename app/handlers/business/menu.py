from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from ._common import PATH_INFO, _show_business_main

router = Router()


@router.callback_query(F.data == "business")
async def cb_business(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.business_path:
        builder = InlineKeyboardBuilder()
        for path_id, info in PATH_INFO.items():
            builder.button(
                text=f"{info['color']} {info['emoji']}  {info['name']}",
                callback_data=f"biz_path:{path_id}"
            )
        builder.adjust(1)
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        try:
            await cb.message.edit_text(
                "🏢 <b>Бизнес — Выбор пути</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Выберите направление развития.\n"
                "⚠️ <b>Выбор нельзя изменить до гибели!</b>\n\n"
                "🟢 ⚖️ <b>Легальный</b>\n"
                "  Стабильный доход, влияние не меняется\n\n"
                "🔴 🕶 <b>Нелегальный</b>\n"
                "  −Влияние при постройке, доход выше\n\n"
                "🔵 🏛 <b>Политика</b>\n"
                "  +Влияние за каждую постройку",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    await _show_business_main(cb, session, user)


@router.callback_query(F.data.startswith("biz_path:"))
async def cb_biz_path(cb: CallbackQuery, session: AsyncSession, user: User):
    path = cb.data.split(":")[1]
    if user.business_path:
        await cb.answer("Путь уже выбран", show_alert=True)
        return
    user.business_path = path
    await session.flush()
    path_info = PATH_INFO.get(path, {})
    await cb.answer(f"✅ {path_info.get('name','')} выбран!")
    await _show_business_main(cb, session, user)
