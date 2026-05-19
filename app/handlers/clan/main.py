import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanMember, ClanInvite
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
from datetime import datetime, timezone

router = Router()


class ClanCreateFSM(StatesGroup):
    waiting_name = State()


@router.callback_query(F.data == "clans_menu")
async def cb_clans_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if clan:
        await _show_clan_main(cb, session, user, clan)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏯 Создать клан", callback_data="clan_create"))
    builder.row(InlineKeyboardButton(text="🔍 Найти клан", callback_data="clan_search:0"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    try:
        await cb.message.edit_text(
            "🏯 <b>Кланы</b>\n\nВы не состоите в клане.\nСоздайте свой или вступите в существующий!",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _show_clan_main(cb: CallbackQuery, session: AsyncSession, user: User, clan: Clan):
    members = await clan_service.get_clan_members(session, clan.id)
    is_owner = clan.owner_id == user.id
    now = datetime.now(timezone.utc)

    from app.models.clan import ClanWar
    active_war = await session.scalar(
        select(ClanWar).where(
            ClanWar.is_finished == False,
            (ClanWar.clan1_id == clan.id) | (ClanWar.clan2_id == clan.id)
        )
    )
    active_auction = await clan_service.get_active_auction(session, clan.id)

    builder = InlineKeyboardBuilder()
    if is_owner:
        builder.row(InlineKeyboardButton(text="📨 Пригласить", callback_data="clan_invite"))
    builder.row(InlineKeyboardButton(text="👥 Участники", callback_data="clan_members"))
    builder.row(InlineKeyboardButton(text="🏦 Казна", callback_data="clan_treasury"))
    builder.row(InlineKeyboardButton(text="🔄 Обмен", callback_data="clan_exchange"))
    builder.row(InlineKeyboardButton(text="🛒 Магазин клана", callback_data="clan_shop"))

    if active_auction:
        remaining = max(0, int((active_auction.ends_at - now).total_seconds()))
        h, m = divmod(remaining // 60, 60)
        builder.row(InlineKeyboardButton(
            text=f"🏛 Аукцион (⏳{h}ч {m}м)",
            callback_data=f"clan_auction:{active_auction.id}"
        ))
    else:
        builder.row(InlineKeyboardButton(text="🏛 Аукцион", callback_data="clan_auction_info"))

    if active_war:
        remaining = max(0, int((active_war.ends_at - now).total_seconds()))
        h, m = divmod(remaining // 60, 60)
        builder.row(InlineKeyboardButton(
            text=f"⚔️ Война (⏳{h}ч {m}м)",
            callback_data=f"clan_war_status:{active_war.id}"
        ))
    else:
        builder.row(InlineKeyboardButton(text="⚔️ Война", callback_data="clan_war"))

    if is_owner:
        builder.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="clan_edit"))
    builder.row(InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    # Улучшения клана (из казны)
    upgrade_lines = []
    if clan.bonus_income_pct: upgrade_lines.append(f"💰 +{clan.bonus_income_pct}%")
    if clan.bonus_ticket_pct: upgrade_lines.append(f"🎟 +{clan.bonus_ticket_pct}%")
    if clan.bonus_train_pct:  upgrade_lines.append(f"🏋 +{clan.bonus_train_pct}%")
    upgrade_str = "\n⚙️ Улучшения: " + " | ".join(upgrade_lines) if upgrade_lines else ""

    # Донат-бонусы
    donat_lines = []
    if clan.donat_income_pct: donat_lines.append(f"💰 +{clan.donat_income_pct}%")
    if clan.donat_ticket_pct: donat_lines.append(f"🎟 +{clan.donat_ticket_pct}%")
    if clan.donat_train_pct:  donat_lines.append(f"🏋 +{clan.donat_train_pct}%")
    donat_str = "\n💎 Донат: " + " | ".join(donat_lines) if donat_lines else ""

    vvip_level = getattr(clan, "vvip_level", 0)
    vvip_str = f"\n👑 VVIP: {vvip_level}" if vvip_level > 0 else ""

    war_str = "\n⚔️ Идёт война!" if active_war else ""

    try:
        await cb.message.edit_text(
            f"🏯 <b>{html.escape(clan.name)}</b>"
            f"{'  👑 Владелец' if is_owner else ''}\n\n"
            f"{'─' * 20}\n"
            f"👥 Участников: {len(members)}/{clan.max_members}\n"
            f"💪 Боевая мощь: {fmt_num(clan.combat_power)}\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin"
            f"{upgrade_str}"
            f"{donat_str}"
            f"{vvip_str}"
            f"{war_str}\n\n"
            f"Выбери действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass

# Участники клана

@router.callback_query(F.data == "clan_members")
async def cb_clan_members(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    lines = [f"👥 <b>Участники клана {html.escape(clan.name)}</b>\n"]
    for m in members:
        target = await session.scalar(select(User).where(User.id == m.user_id))
        if not target:
            continue
        crown = "👑 " if clan.owner_id == target.id else ""
        username_str = f" @{target.username}" if target.username else ""
        lines.append(
            f"{crown}<b>{html.escape(target.full_name)}</b>{username_str}\n"
            f"  💪 {fmt_num(target.combat_power)}"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass

# ── Создание ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_create")
async def cb_clan_create(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ClanCreateFSM.waiting_name)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clans_menu"))
    try:
        await cb.message.edit_text(
            "🏯 <b>Создание клана</b>\n\nВведите название клана (2-32 символа):",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(ClanCreateFSM.waiting_name)
async def msg_clan_name(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    result = await clan_service.create_clan(session, user, message.text.strip())
    if result["ok"]:
        await message.answer(
            f"✅ Клан <b>{html.escape(result['name'])}</b> создан!\n\nВы стали его владельцем.",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ {result['reason']}")


# ── Поиск ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_search:"))
async def cb_clan_search(cb: CallbackQuery, session: AsyncSession, user: User, page: int = None):
    # Если page не передан явно (обычный callback), берём из cb.data
    if page is None:
        page = int(cb.data.split(":")[1])

    PAGE = 8
    clans = await clan_service.get_top_clans(session, limit=50)
    total = len(clans)
    page_clans = clans[page * PAGE:(page + 1) * PAGE]

    # Проверяем есть ли у пользователя активная заявка
    existing_request = await session.scalar(
        select(ClanInvite).where(
            ClanInvite.to_user_id == user.id,
            ClanInvite.is_pending == True,
            ClanInvite.invite_type == "request",
        )
    )

    builder = InlineKeyboardBuilder()
    for clan in page_clans:
        members = await clan_service.get_clan_members(session, clan.id)
        full = len(members) >= clan.max_members
        icon = "🔒" if full else "🏯"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {html.escape(clan.name)} | 💪{fmt_num(clan.combat_power)} | 👥{len(members)}/{clan.max_members}",
            callback_data=f"clan_view:{clan.id}"
        ))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"clan_search:{page-1}"))
    if (page + 1) * PAGE < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"clan_search:{page+1}"))
    if nav:
        builder.row(*nav)

    if existing_request:
        builder.row(InlineKeyboardButton(
            text="❌ Отменить мою заявку",
            callback_data="clan_cancel_request"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            f"🔍 <b>Все кланы</b> (топ по силе)\n\n"
            f"{'⏳ У вас есть активная заявка' if existing_request else 'Нажми на клан чтобы подать заявку:'}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_view:"))
async def cb_clan_view(cb: CallbackQuery, session: AsyncSession, user: User):
    clan_id = int(cb.data.split(":")[1])
    clan = await session.scalar(select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    my_clan = await clan_service.get_user_clan(session, user.id)

    # Проверяем заявку
    existing = await session.scalar(
        select(ClanInvite).where(
            ClanInvite.to_user_id == user.id,
            ClanInvite.is_pending == True,
        )
    )

    builder = InlineKeyboardBuilder()
    if not my_clan:
        if existing and existing.clan_id == clan_id and existing.invite_type == "request":
            builder.row(InlineKeyboardButton(text="⏳ Заявка отправлена", callback_data="noop_clan"))
            builder.row(InlineKeyboardButton(text="❌ Отменить заявку", callback_data="clan_cancel_request"))
        elif not existing and len(members) < clan.max_members:
            builder.row(InlineKeyboardButton(
                text="📨 Подать заявку",
                callback_data=f"clan_request:{clan_id}"
            ))
        elif existing:
            builder.row(InlineKeyboardButton(text="⏳ У вас есть активная заявка", callback_data="noop_clan"))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_search:0"))

    # Бонусы клана
    bonuses = []
    if clan.bonus_income_pct: bonuses.append(f"💰 +{clan.bonus_income_pct}% доход")
    if clan.bonus_ticket_pct: bonuses.append(f"🎟 +{clan.bonus_ticket_pct}% тикет")
    if clan.bonus_train_pct:  bonuses.append(f"🏋 +{clan.bonus_train_pct}% трен.")
    bonus_str = "\n" + " | ".join(bonuses) if bonuses else ""

    try:
        await cb.message.edit_text(
            f"🏯 <b>{html.escape(clan.name)}</b>\n\n"
            f"👥 Участников: {len(members)}/{clan.max_members}\n"
            f"💪 Боевая мощь: {fmt_num(clan.combat_power)}\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin"
            f"{bonus_str}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_request:"))
async def cb_clan_request(cb: CallbackQuery, session: AsyncSession, user: User):
    clan_id = int(cb.data.split(":")[1])
    clan = await session.scalar(select(Clan).where(Clan.id == clan_id))
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return

    result = await clan_service.request_join(session, clan, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    from app.bot_instance import get_bot
    bot = get_bot()
    owner = await session.scalar(select(User).where(User.id == clan.owner_id))
    if bot and owner:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅ Принять", callback_data=f"clan_accept_req:{result['request_id']}"
        ))
        builder.row(InlineKeyboardButton(
            text="❌ Отклонить", callback_data=f"clan_decline_req:{result['request_id']}"
        ))
        try:
            await bot.send_message(
                owner.tg_id,
                f"📨 <b>Заявка в клан {html.escape(clan.name)}</b>\n\n"
                f"👤 {html.escape(user.full_name)}"
                f"{f' (@{user.username})' if user.username else ''}\n"
                f"💪 Мощь: {fmt_num(user.combat_power)}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.answer("✅ Заявка отправлена! Ожидайте ответа владельца.", show_alert=True)
    await cb_clan_view(cb, session, user)


# ── /topclan ──────────────────────────────────────────────────────────────────

@router.message(Command("topclan"))
async def cmd_topclan(message: Message, session: AsyncSession, user: User):
    clans = await clan_service.get_top_clans(session, limit=10)
    lines = ["🏆 <b>Топ-10 кланов по боевой мощи</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, clan in enumerate(clans):
        members = await clan_service.get_clan_members(session, clan.id)
        medal = medals.get(i, f"{i+1}.")
        lines.append(
            f"{medal} <b>{html.escape(clan.name)}</b>\n"
            f"   💪 {fmt_num(clan.combat_power)} | 👥 {len(members)}/{clan.max_members}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "noop_clan")
async def cb_noop_clan(cb: CallbackQuery):
    await cb.answer()