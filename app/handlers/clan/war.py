import html
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanWar
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
from datetime import datetime, timezone

router = Router()


class WarFSM(StatesGroup):
    waiting_war_clan = State()


@router.callback_query(F.data == "clan_war")
async def cb_clan_war(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        await cb.answer("Только владелец может начать войну", show_alert=True)
        return

    # Проверяем нет ли активной войны
    active = await session.scalar(
        select(ClanWar).where(
            ClanWar.is_finished == False,
            (ClanWar.clan1_id == clan.id) | (ClanWar.clan2_id == clan.id)
        )
    )
    if active:
        cb.data = f"clan_war_status:{active.id}"
        await cb_clan_war_status(cb, session, user)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚔️ Война вооружения (6ч)",
        callback_data="clan_war_type:power"
    ))
    builder.row(InlineKeyboardButton(
        text="💰 Война богатств (4ч)",
        callback_data="clan_war_type:treasury"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            "⚔️ <b>Война кланов</b>\n\n"
            "⚔️ <b>Война вооружения</b> — у кого больше вырастет боевая мощь за 6 часов\n"
            "  Победитель получает 10% от своего прироста в казну\n\n"
            "💰 <b>Война богатств</b> — у кого будет больше прироста казны за 4 часа\n"
            "  Победитель получает 10% от своего прироста в казну\n\n"
            "Проигравший тоже получает 5% от прироста.\n\n"
            "Выбери тип войны:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_war_type:"))
async def cb_clan_war_type(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    war_type = cb.data.split(":")[1]
    await state.set_state(WarFSM.waiting_war_clan)
    await state.update_data(war_type=war_type)

    clans = await clan_service.get_top_clans(session, limit=20)
    my_clan = await clan_service.get_user_clan(session, user.id)

    # Один запрос вместо N: клан ID уже занятых войной
    clan_ids = [clan.id for clan in clans]
    busy_wars_r = await session.execute(
        select(ClanWar.clan1_id, ClanWar.clan2_id).where(
            ClanWar.is_finished == False,
            (ClanWar.clan1_id.in_(clan_ids)) | (ClanWar.clan2_id.in_(clan_ids)),
        )
    )
    busy_clan_ids: set[int] = set()
    for c1, c2 in busy_wars_r.all():
        busy_clan_ids.add(c1)
        busy_clan_ids.add(c2)

    builder = InlineKeyboardBuilder()
    for clan in clans:
        if my_clan and clan.id == my_clan.id:
            continue
        is_busy = clan.id in busy_clan_ids
        icon = "⚔️" if not is_busy else "🔒"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {html.escape(clan.name)} | 💪{fmt_num(clan.combat_power)}",
            callback_data=f"clan_war_start:{clan.id}:{war_type}" if not is_busy else "noop_clan"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_war"))

    type_name = "вооружения" if war_type == "power" else "богатств"
    try:
        await cb.message.edit_text(
            f"⚔️ <b>Война {type_name}</b>\n\nВыбери противника:\n🔒 — уже в войне",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_war_start:"))
async def cb_clan_war_start(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    parts = cb.data.split(":")
    target_clan_id = int(parts[1])
    war_type = parts[2]

    my_clan = await clan_service.get_user_clan(session, user.id)
    target_clan = await session.scalar(select(Clan).where(Clan.id == target_clan_id))

    if not my_clan or not target_clan:
        await cb.answer("Клан не найден", show_alert=True)
        return

    result = await clan_service.start_war(session, my_clan, target_clan, war_type, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    ends_at = result["ends_at"]
    now = datetime.now(timezone.utc)
    h = int((ends_at - now).total_seconds() // 3600)
    await cb.answer(f"⚔️ Война началась! Длится {h} часов.", show_alert=True)

    # Уведомляем врага
    from app.bot_instance import get_bot
    bot = get_bot()
    if bot:
        type_name = "вооружения" if war_type == "power" else "богатств"
        # Уведомляем всех участников вражеского клана (один запрос вместо N)
        from app.models.clan import ClanMember
        from app.scheduler.tasks.notifications import _send_notifications
        tg_ids_r = await session.execute(
            select(User.tg_id)
            .join(ClanMember, ClanMember.user_id == User.id)
            .where(ClanMember.clan_id == target_clan.id)
        )
        tg_ids = list(tg_ids_r.scalars())
        await _send_notifications(
            bot, tg_ids,
            f"⚔️ <b>Война началась!</b>\n\n"
            f"Клан <b>{html.escape(my_clan.name)}</b> объявил войну вашему клану!\n"
            f"Тип: война {type_name}\n"
            f"Длится {h} часов.",
        )

    from app.handlers.clan.main import cb_clans_menu
    await cb_clans_menu(cb, session, user)


@router.callback_query(F.data.startswith("clan_war_status:"))
async def cb_clan_war_status(cb: CallbackQuery, session: AsyncSession, user: User):
    war_id = int(cb.data.split(":")[1])
    war = await session.scalar(select(ClanWar).where(ClanWar.id == war_id))
    if not war:
        await cb.answer("Война не найдена", show_alert=True)
        return

    clan1 = await session.scalar(select(Clan).where(Clan.id == war.clan1_id))
    clan2 = await session.scalar(select(Clan).where(Clan.id == war.clan2_id))

    now = datetime.now(timezone.utc)
    remaining = max(0, int((war.ends_at - now).total_seconds()))
    h, m = divmod(remaining // 60, 60)

    if war.war_type == "power":
        cur1 = clan1.combat_power if clan1 else 0
        cur2 = clan2.combat_power if clan2 else 0
        diff1 = cur1 - war.clan1_start
        diff2 = cur2 - war.clan2_start
        label = "💪 Прирост мощи"
        stat_str = (
            f"{label}:\n"
            f"  🏯 {html.escape(clan1.name) if clan1 else '?'}: +{fmt_num(diff1)}\n"
            f"  🏯 {html.escape(clan2.name) if clan2 else '?'}: +{fmt_num(diff2)}"
        )
    else:
        cur1 = clan1.treasury if clan1 else 0
        cur2 = clan2.treasury if clan2 else 0
        diff1 = cur1 - war.clan1_start
        diff2 = cur2 - war.clan2_start
        label = "🏦 Прирост казны"
        stat_str = (
            f"{label}:\n"
            f"  🏯 {html.escape(clan1.name) if clan1 else '?'}: +{fmt_num(diff1)}\n"
            f"  🏯 {html.escape(clan2.name) if clan2 else '?'}: +{fmt_num(diff2)}"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"clan_war_status:{war_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    type_name = "вооружения" if war.war_type == "power" else "богатств"
    status = "✅ Завершена" if war.is_finished else f"⏳ До конца: {h}ч {m}м"

    if war.is_finished and war.winner_clan_id:
        winner = clan1 if war.winner_clan_id == war.clan1_id else clan2
        status += f"\n🏆 Победитель: {html.escape(winner.name) if winner else '?'}"

    try:
        await cb.message.edit_text(
            f"⚔️ <b>Война {type_name}</b>\n\n"
            f"{stat_str}\n\n"
            f"{status}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass