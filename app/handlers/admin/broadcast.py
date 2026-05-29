from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num
from app.handlers.admin._common import is_admin, AdminFSM

router = Router()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_broadcast)
    try:
        await cb.message.edit_text(
            "📢 <b>Рассылка всем игрокам</b>\n\n"
            "Введите текст сообщения.\nПоддерживается HTML-форматирование.",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_broadcast)
async def msg_broadcast(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    text = message.text.strip()
    from app.models.user import User as UserModel
    users_r = await session.execute(select(UserModel))
    all_users = users_r.scalars().all()
    bot = message.bot
    sent = failed = blocked = 0
    for u in all_users:
        try:
            await bot.send_message(
                u.tg_id,
                f"📢 <b>Сообщение от администрации</b>\n\n{text}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "forbidden" in err or "deactivated" in err:
                blocked += 1
            else:
                failed += 1
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"👥 Всего: {len(all_users)}\n"
        f"✅ Отправлено: {sent}\n"
        f"🚫 Заблокировали: {blocked}\n"
        f"❌ Ошибки: {failed}",
        reply_markup=back_kb("admin_main"),
    )


@router.callback_query(F.data == "admin_bulk")
async def cb_admin_bulk(cb: CallbackQuery, user: User):
    if not is_admin(user.tg_id):
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Выдать монеты всем", callback_data="admin_bulk_coins"))
    builder.row(InlineKeyboardButton(text="🎟 Выдать тикеты всем", callback_data="admin_bulk_tickets"))
    builder.row(InlineKeyboardButton(text="🔄 Пересчитать бонусы всем", callback_data="admin_bulk_reapply"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
    try:
        await cb.message.edit_text(
            "👥 <b>Действия со всеми игроками</b>\n\nВыбери действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_bulk_coins")
async def cb_admin_bulk_coins(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_bulk_coins)
    try:
        await cb.message.edit_text(
            "💰 Введите количество монет для всех игроков:",
            reply_markup=back_kb("admin_bulk"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_bulk_coins)
async def msg_bulk_coins(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    from app.models.user import User as UserModel
    users_r = await session.execute(select(UserModel))
    users = users_r.scalars().all()
    for u in users:
        u.nh_coins += amount
    await session.flush()
    await message.answer(
        f"✅ Выдано {fmt_num(amount)} монет {len(users)} игрокам!",
        reply_markup=back_kb("admin_main"),
    )


@router.callback_query(F.data == "admin_bulk_tickets")
async def cb_admin_bulk_tickets(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(AdminFSM.waiting_bulk_tickets)
    try:
        await cb.message.edit_text(
            "🎟 Введите количество тикетов для всех игроков:",
            reply_markup=back_kb("admin_bulk"),
        )
    except Exception:
        pass


@router.message(AdminFSM.waiting_bulk_tickets)
async def msg_bulk_tickets(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число")
        return
    from app.models.user import User as UserModel
    users_r = await session.execute(select(UserModel))
    users = users_r.scalars().all()
    from app.config.game_balance import ticket_hard_cap
    for u in users:
        u.tickets = min(u.tickets + count, ticket_hard_cap(u))
    await session.flush()
    await message.answer(
        f"✅ Выдано {count} тикетов {len(users)} игрокам!",
        reply_markup=back_kb("admin_main"),
    )


@router.callback_query(F.data == "admin_bulk_reapply")
async def cb_admin_bulk_reapply(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    from app.models.user import User as UserModel
    from app.services.title_service import title_service as ts
    users_r = await session.execute(select(UserModel))
    users = users_r.scalars().all()
    for u in users:
        await ts.reapply_all_titles(session, u)
    await cb.answer(f"✅ Бонусы пересчитаны для {len(users)} игроков", show_alert=True)
    try:
        await cb.message.edit_text(
            f"✅ Бонусы пересчитаны для {len(users)} игроков",
            reply_markup=back_kb("admin_bulk"),
        )
    except Exception:
        pass
