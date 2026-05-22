from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.services.admin_service import admin_service
from app.utils.keyboards.admin import admin_main_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import phase_label
from app.handlers.admin._common import is_admin

router = Router()


@router.callback_query(F.data == "admin_main")
async def cb_admin_main(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    try:
        await cb.message.edit_text(
            "🔧 <b>Панель администратора</b>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    stats = await admin_service.get_stats(session)
    phase_lines = "\n".join(
        f"  {phase_label(p)}: {c}" for p, c in stats["phases"].items()
    )
    from app.models.game_version import GameVersion
    gv_result = await session.execute(
        select(GameVersion).order_by(GameVersion.applied_at.desc()).limit(1)
    )
    gv = gv_result.scalar_one_or_none()
    version_str = f"Версия: {gv.version}" if gv else "Версия: не задана"

    try:
        await cb.message.edit_text(
            f"📊 <b>Статистика</b>\n\n"
            f"Всего игроков: {stats['total']}\n"
            f"⚔️ С боевой мощью > 0: {stats['with_power']}\n"
            f"🔖 {version_str}\n\n"
            f"По фазам:\n{phase_lines}",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass
