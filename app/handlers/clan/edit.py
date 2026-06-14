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
from app.models.clan import Clan, ClanMember
from app.services.clan import clan_service
from app.utils.formatters import fmt_num

router = Router()


class EditFSM(StatesGroup):
    waiting_rename = State()


@router.callback_query(F.data == "clan_edit")
async def cb_clan_edit(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        await cb.answer("Только для владельца", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Переименовать", callback_data="clan_rename"))
    builder.row(InlineKeyboardButton(text="👤 Передать права", callback_data="clan_transfer"))

    for m in members:
        if m.user_id == user.id:
            continue
        target = await session.scalar(select(User).where(User.id == m.user_id))
        if target:
            builder.row(InlineKeyboardButton(
                text=f"🚫 Выгнать {html.escape(target.full_name)}",
                callback_data=f"clan_kick:{target.id}"
            ))

    builder.row(InlineKeyboardButton(text="🗑 Удалить клан", callback_data="clan_delete"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            f"✏️ <b>Редактирование клана {html.escape(clan.name)}</b>\n\n"
            f"👥 Участников: {len(members)}/{clan.max_members}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "clan_rename")
async def cb_clan_rename(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditFSM.waiting_rename)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_edit"))
    try:
        await cb.message.edit_text(
            "✏️ Введите новое название клана (2-32 символа):",
            reply_markup=cancel_kb.as_markup(),
        )
    except Exception:
        pass


@router.message(EditFSM.waiting_rename)
async def msg_clan_rename(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return
    result = await clan_service.rename_clan(session, clan, user, message.text.strip())
    if result["ok"]:
        await message.answer(
            f"✅ Клан переименован в <b>{html.escape(clan.name)}</b>!",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ {result['reason']}")


@router.callback_query(F.data == "clan_kick_menu")
async def cb_clan_kick_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return
    my_member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    my_rank = my_member.rank if my_member else "member"
    if my_rank not in ("owner", "deputy"):
        await cb.answer("Недостаточно прав", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    builder = InlineKeyboardBuilder()
    for m in members:
        if m.user_id == user.id:
            continue
        if my_rank == "deputy" and m.user_id == clan.owner_id:
            continue
        target = await session.scalar(select(User).where(User.id == m.user_id))
        if target:
            builder.row(InlineKeyboardButton(
                text=f"🚫 {html.escape(target.full_name)}",
                callback_data=f"clan_kick:{target.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            f"🚫 <b>Исключить участника</b>\n\n"
            f"👥 В клане: {len(members)}/{clan.max_members}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_kick:"))
async def cb_clan_kick(cb: CallbackQuery, session: AsyncSession, user: User):
    target_id = int(cb.data.split(":")[1])
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    result = await clan_service.kick_member(session, clan, user, target_id)
    if result["ok"]:
        await cb.answer("✅ Игрок исключён из клана", show_alert=True)
        from app.bot_instance import get_bot
        bot = get_bot()
        target = await session.scalar(select(User).where(User.id == target_id))
        if bot and target:
            try:
                await bot.send_message(
                    target.tg_id,
                    f"🚫 Вы были исключены из клана <b>{html.escape(clan.name)}</b>.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        my_member = await session.scalar(
            select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
        )
        my_rank = my_member.rank if my_member else "member"
        if my_rank == "owner":
            await cb_clan_edit(cb, session, user)
        else:
            await cb_clan_kick_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "clan_transfer")
async def cb_clan_transfer(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        return

    members = await clan_service.get_clan_members(session, clan.id)
    builder = InlineKeyboardBuilder()
    for m in members:
        if m.user_id == user.id:
            continue
        target = await session.scalar(select(User).where(User.id == m.user_id))
        if target:
            builder.row(InlineKeyboardButton(
                text=f"👑 {html.escape(target.full_name)} | 💪{fmt_num(target.combat_power)}",
                callback_data=f"clan_transfer_to:{target.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_edit"))

    try:
        await cb.message.edit_text(
            "👑 Выбери нового владельца клана:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_transfer_to:"))
async def cb_clan_transfer_to(cb: CallbackQuery, session: AsyncSession, user: User):
    new_owner_id = int(cb.data.split(":")[1])
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    result = await clan_service.transfer_ownership(session, clan, user, new_owner_id)
    if result["ok"]:
        new_owner = await session.scalar(select(User).where(User.id == new_owner_id))
        await cb.answer(
            f"✅ Права переданы {html.escape(new_owner.full_name) if new_owner else ''}!",
            show_alert=True
        )
        # Показываем меню клана через импорт
        from app.handlers.clan.main import cb_clans_menu
        await cb_clans_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "clan_delete")
async def cb_clan_delete(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚠️ Подтвердить удаление",
        callback_data="clan_delete_confirm"
    ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_edit"))

    try:
        await cb.message.edit_text(
            f"🗑 <b>Удаление клана {html.escape(clan.name)}</b>\n\n"
            f"⚠️ Все участники будут исключены!\nПодтвердить?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "clan_delete_confirm")
async def cb_clan_delete_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    members = await clan_service.get_clan_members(session, clan.id)
    clan_name = clan.name

    result = await clan_service.delete_clan(session, clan, user)
    if result["ok"]:
        await cb.answer(f"✅ Клан {clan_name} удалён", show_alert=True)
        from app.bot_instance import get_bot
        bot = get_bot()
        for m in members:
            if m.user_id == user.id:
                continue
            target = await session.scalar(select(User).where(User.id == m.user_id))
            if bot and target:
                try:
                    await bot.send_message(
                        target.tg_id,
                        f"🗑 Клан <b>{html.escape(clan_name)}</b> был удалён владельцем.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        from app.handlers.clan.main import cb_clans_menu
        await cb_clans_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "clan_leave")
async def cb_clan_leave(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    if clan.owner_id == user.id:
        members = await clan_service.get_clan_members(session, clan.id)
        others = [m for m in members if m.user_id != user.id]
        if others:
            builder = InlineKeyboardBuilder()
            for m in others:
                target = await session.scalar(select(User).where(User.id == m.user_id))
                if target:
                    builder.row(InlineKeyboardButton(
                        text=f"👑 Передать {html.escape(target.full_name)}",
                        callback_data=f"clan_leave_transfer:{target.id}"
                    ))
            builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clans_menu"))
            try:
                await cb.message.edit_text(
                    "🚪 Вы владелец. Передайте права перед выходом:",
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML",
                )
            except Exception:
                pass
            return

    result = await clan_service.leave_clan(session, user)
    if result["ok"]:
        await cb.answer("✅ Вы покинули клан", show_alert=True)
        from app.handlers.clan.main import cb_clans_menu
        await cb_clans_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data.startswith("clan_leave_transfer:"))
async def cb_clan_leave_transfer(cb: CallbackQuery, session: AsyncSession, user: User):
    new_owner_id = int(cb.data.split(":")[1])
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    await clan_service.transfer_ownership(session, clan, user, new_owner_id)
    result = await clan_service.leave_clan(session, user)

    if result["ok"]:
        await cb.answer("✅ Права переданы, вы покинули клан", show_alert=True)
        from app.handlers.clan.main import cb_clans_menu
        await cb_clans_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)