import html

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.services.admin_service import admin_service
from app.utils.keyboards.admin import admin_main_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, phase_label
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


@router.callback_query(F.data.startswith("admin_real_top"))
async def cb_admin_real_top(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    parts = cb.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0
    PAGE = 20

    from sqlalchemy import func as _func
    total = await session.scalar(select(_func.count(User.id))) or 0
    # Всё топ без фильтров (включая скрытых)
    rows = (await session.execute(
        select(
            User.id, User.tg_id, User.full_name,
            User.combat_power, User.phase,
            User.shadow_stealth_active, User.path_unique_2,
        )
        .order_by(User.combat_power.desc())
        .offset(page * PAGE)
        .limit(PAGE)
    )).all()

    total_pages = max(1, (total + PAGE - 1) // PAGE)
    lines = [f"👁 <b>Реальный топ</b> (стр. {page+1}/{total_pages}, всего {total})\n"]
    start = page * PAGE + 1
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, r in enumerate(rows):
        rank = start + i
        medal = medals.get(i if page == 0 else -1, f"#{rank}")
        hidden = " 🌑" if (r.shadow_stealth_active or r.path_unique_2) else ""
        phase_lbl = phase_label(r.phase)
        lines.append(
            f"{medal} <b>{html.escape(r.full_name)}</b>{hidden}\n"
            f"   💪 {fmt_num(r.combat_power)} | {phase_lbl} | id:{r.tg_id}"
        )

    builder = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_real_top:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_real_top:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


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
