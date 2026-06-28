import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from app.models.user import User
from app.models.clan import Clan, ClanMember
from app.utils.keyboards.common import back_kb
from app.handlers.admin._common import is_admin
from app.services.clan import clan_service
from app.utils.formatters import fmt_num

router = Router()


class ClanOwnerFSM(StatesGroup):
    waiting_clan_search = State()


RANK_LABELS = {
    "owner": "👑",
    "deputy": "🛡",
    "captain": "⚔️",
    "member": "👤",
}


@router.callback_query(F.data == "admin_clan_owner")
async def cb_admin_clan_owner(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.set_state(ClanOwnerFSM.waiting_clan_search)
    try:
        await cb.message.edit_text(
            "👑 <b>Смена главы клана</b>\n\nВведите название клана:",
            reply_markup=back_kb("admin_main"),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(ClanOwnerFSM.waiting_clan_search)
async def msg_clan_owner_search(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    await state.clear()
    name = message.text.strip()
    clan = await session.scalar(sa_select(Clan).where(Clan.name == name))
    if not clan:
        result = await session.execute(
            sa_select(Clan).where(Clan.name.ilike(f"%{name}%")).limit(10)
        )
        clans = result.scalars().all()
        if not clans:
            await message.answer("❌ Клан не найден", reply_markup=back_kb("admin_main"))
            return
        if len(clans) == 1:
            clan = clans[0]
        else:
            builder = InlineKeyboardBuilder()
            for c in clans:
                builder.row(InlineKeyboardButton(
                    text=c.name,
                    callback_data=f"adm_clan_owner_view:{c.id}"
                ))
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
            await message.answer(
                "🔍 Найдено несколько кланов:",
                reply_markup=builder.as_markup(),
            )
            return
    await _show_clan_owner_panel(message, session, clan)


@router.callback_query(F.data.startswith("adm_clan_owner_view:"))
async def cb_adm_clan_owner_view(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    clan_id = int(cb.data.split(":")[1])
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return
    await _show_clan_owner_panel(cb.message, session, clan)


async def _show_clan_owner_panel(message, session: AsyncSession, clan: Clan):
    members_result = await session.execute(
        sa_select(ClanMember).where(ClanMember.clan_id == clan.id)
    )
    members = members_result.scalars().all()
    user_ids = [m.user_id for m in members]
    users_result = await session.execute(
        sa_select(User).where(User.id.in_(user_ids))
    )
    users_map = {u.id: u for u in users_result.scalars().all()}
    rank_map = {m.user_id: m.rank for m in members}

    builder = InlineKeyboardBuilder()
    for m in members:
        u = users_map.get(m.user_id)
        if not u:
            continue
        if m.user_id == clan.owner_id:
            continue  # текущий владелец не в списке выбора
        rank_icon = RANK_LABELS.get(m.rank, "👤")
        builder.row(InlineKeyboardButton(
            text=f"{rank_icon} {html.escape(u.full_name)} | 💪{fmt_num(u.combat_power)}",
            callback_data=f"adm_clan_owner_confirm:{clan.id}:{u.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))

    current_owner = users_map.get(clan.owner_id)
    owner_name = html.escape(current_owner.full_name) if current_owner else f"id={clan.owner_id}"

    text = (
        f"👑 <b>Смена главы клана</b>\n\n"
        f"🏯 Клан: <b>{html.escape(clan.name)}</b>\n"
        f"👑 Текущий владелец: <b>{owner_name}</b>\n"
        f"👥 Участников: {len(members)}\n\n"
        f"Выберите нового владельца:"
    )
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_clan_owner_confirm:"))
async def cb_adm_clan_owner_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    clan_id, new_owner_id = int(parts[1]), int(parts[2])
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return
    new_owner = await session.scalar(sa_select(User).where(User.id == new_owner_id))
    if not new_owner:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data=f"adm_clan_owner_apply:{clan_id}:{new_owner_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"adm_clan_owner_view:{clan_id}"
    ))

    old_owner = await session.scalar(sa_select(User).where(User.id == clan.owner_id))
    old_name = html.escape(old_owner.full_name) if old_owner else f"id={clan.owner_id}"

    try:
        await cb.message.edit_text(
            f"👑 <b>Подтверждение смены главы</b>\n\n"
            f"🏯 Клан: <b>{html.escape(clan.name)}</b>\n"
            f"❌ Бывший владелец: <b>{old_name}</b> → станет участником\n"
            f"✅ Новый владелец: <b>{html.escape(new_owner.full_name)}</b>\n\n"
            f"Подтвердить?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_clan_owner_apply:"))
async def cb_adm_clan_owner_apply(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    clan_id, new_owner_id = int(parts[1]), int(parts[2])
    clan = await session.scalar(sa_select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return

    old_owner_id = clan.owner_id
    result = await clan_service.admin_transfer_ownership(session, clan, new_owner_id)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()

    new_owner = await session.scalar(sa_select(User).where(User.id == new_owner_id))
    old_owner = await session.scalar(sa_select(User).where(User.id == old_owner_id))
    await cb.answer(
        f"✅ Глава клана {clan.name} сменён на {new_owner.full_name if new_owner else ''}!",
        show_alert=True,
    )

    # Уведомляем старого и нового владельца
    from app.bot_instance import get_bot
    bot = get_bot()
    if bot:
        if old_owner:
            try:
                await bot.send_message(
                    old_owner.tg_id,
                    f"👑 Администратор передал главу клана <b>{html.escape(clan.name)}</b>.\n"
                    f"Вы стали обычным участником.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        if new_owner:
            try:
                await bot.send_message(
                    new_owner.tg_id,
                    f"👑 Администратор назначил вас главой клана <b>{html.escape(clan.name)}</b>!",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    # Обновляем клан из БД и возвращаем к панели
    await session.refresh(clan)
    await _show_clan_owner_panel(cb.message, session, clan)
