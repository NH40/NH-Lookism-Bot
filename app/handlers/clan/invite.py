import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanInvite, ClanMember
from app.services.clan import clan_service
from app.utils.formatters import fmt_num

router = Router()


class InviteFSM(StatesGroup):
    waiting_username = State()


@router.callback_query(F.data == "clan_invite")
async def cb_clan_invite(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return
    my_member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    my_rank = my_member.rank if my_member else "member"
    if my_rank not in ("owner", "deputy"):
        await cb.answer("Только владелец или заместитель может управлять приглашениями", show_alert=True)
        return

    # Входящие заявки
    pending_r = await session.execute(
        select(ClanInvite).where(
            ClanInvite.clan_id == clan.id,
            ClanInvite.invite_type == "request",
            ClanInvite.is_pending == True,
        )
    )
    requests = pending_r.scalars().all()

    builder = InlineKeyboardBuilder()

    if requests:
        builder.row(InlineKeyboardButton(
            text=f"📋 Заявки ({len(requests)})",
            callback_data="noop_clan"
        ))
        for req in requests:
            requester = await session.scalar(select(User).where(User.id == req.from_user_id))
            if requester:
                builder.row(InlineKeyboardButton(
                    text=f"✅ {html.escape(requester.full_name)} | 💪{fmt_num(requester.combat_power)}",
                    callback_data=f"clan_accept_req:{req.id}"
                ))
                builder.row(InlineKeyboardButton(
                    text=f"❌ Отклонить {html.escape(requester.full_name)}",
                    callback_data=f"clan_decline_req:{req.id}"
                ))

    builder.row(InlineKeyboardButton(
        text="📨 Пригласить по @username",
        callback_data="clan_invite_input"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    members = await clan_service.get_clan_members(session, clan.id)
    requests_str = f"\n📋 Входящих заявок: <b>{len(requests)}</b>" if requests else ""

    try:
        await cb.message.edit_text(
            f"📨 <b>Управление участниками</b>\n\n"
            f"👥 В клане: {len(members)}/{clan.max_members}"
            f"{requests_str}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "clan_invite_input")
async def cb_clan_invite_input(cb: CallbackQuery, state: FSMContext):
    await state.set_state(InviteFSM.waiting_username)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_invite"))
    try:
        await cb.message.edit_text(
            "📨 Введите @username игрока которого хотите пригласить:",
            reply_markup=cancel_kb.as_markup(),
        )
    except Exception:
        pass


@router.message(InviteFSM.waiting_username)
async def msg_invite_username(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    result = await clan_service.invite_user(session, clan, user, message.text.strip())
    if not result["ok"]:
        await message.answer(f"❌ {result['reason']}")
        return

    to_user = result["to_user"]
    from app.bot_instance import get_bot
    bot = get_bot()
    if bot:
        builder = InlineKeyboardBuilder()
        invite_id = result["invite_id"]
        builder.row(InlineKeyboardButton(text="✅ Принять", callback_data=f"clan_accept:{invite_id}"))
        builder.row(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"clan_decline:{invite_id}"))
        try:
            await bot.send_message(
                to_user.tg_id,
                f"📨 <b>Приглашение в клан!</b>\n\n"
                f"Клан: <b>{html.escape(clan.name)}</b>\n"
                f"От: {html.escape(user.full_name)}\n"
                f"💪 Мощь клана: {fmt_num(clan.combat_power)}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await message.answer(
        f"✅ Приглашение отправлено <b>{html.escape(to_user.full_name)}</b>!",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("clan_accept:"))
async def cb_clan_accept(cb: CallbackQuery, session: AsyncSession, user: User):
    invite_id = int(cb.data.split(":")[1])
    result = await clan_service.accept_invite(session, invite_id, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return
    clan = result["clan"]
    await cb.answer(f"✅ Вы вступили в клан {clan.name}!", show_alert=True)
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_decline:"))
async def cb_clan_decline(cb: CallbackQuery, session: AsyncSession, user: User):
    invite_id = int(cb.data.split(":")[1])
    await clan_service.decline_invite(session, invite_id)
    await cb.answer("❌ Приглашение отклонено")
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_accept_req:"))
async def cb_clan_accept_req(cb: CallbackQuery, session: AsyncSession, user: User):
    invite_id = int(cb.data.split(":")[1])
    invite = await session.scalar(select(ClanInvite).where(ClanInvite.id == invite_id))
    if not invite:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    requester = await session.scalar(select(User).where(User.id == invite.from_user_id))
    if not requester:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    result = await clan_service.accept_invite(session, invite_id, requester)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(f"✅ {requester.full_name} принят в клан!", show_alert=True)

    from app.bot_instance import get_bot
    bot = get_bot()
    if bot:
        try:
            await bot.send_message(
                requester.tg_id,
                f"✅ <b>Ваша заявка одобрена!</b>\n\n"
                f"Вы вступили в клан <b>{html.escape(result['clan'].name)}</b>!",
                parse_mode="HTML",
            )
        except Exception:
            pass

    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_decline_req:"))
async def cb_clan_decline_req(cb: CallbackQuery, session: AsyncSession, user: User):
    invite_id = int(cb.data.split(":")[1])
    invite = await session.scalar(select(ClanInvite).where(ClanInvite.id == invite_id))
    if not invite:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    requester = await session.scalar(select(User).where(User.id == invite.from_user_id))
    await clan_service.decline_invite(session, invite_id)
    await cb.answer("❌ Заявка отклонена")

    from app.bot_instance import get_bot
    bot = get_bot()
    if bot and requester:
        try:
            await bot.send_message(
                requester.tg_id,
                "❌ <b>Ваша заявка в клан отклонена.</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    try:
        await cb.message.delete()
    except Exception:
        pass


# Единственный обработчик отмены заявки, без дублирования clan_search:
@router.callback_query(F.data == "clan_cancel_request")
async def cb_clan_cancel_request(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await clan_service.cancel_request(session, user)
    if result["ok"]:
        await cb.answer("✅ Заявка отменена. Теперь можно подать в другой клан.", show_alert=True)
        from app.handlers.clan.main import cb_clan_search
        # Передаём page=0, не трогая объект cb (frozen)
        await cb_clan_search(cb, session, user, page=0)
    else:
        await cb.answer(result["reason"], show_alert=True)