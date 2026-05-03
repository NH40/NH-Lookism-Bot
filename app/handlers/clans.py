import json
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
from app.models.clan import Clan, ClanMember, ClanInvite, ClanAuction
from app.services.clan_service import clan_service
from app.utils.formatters import fmt_num
from datetime import datetime, timezone
from app.constants.clan import CLAN_SHOP_ITEMS, CLAN_SHOP_MAP, CLAN_SHOP_CATEGORIES

router = Router()


class ClanFSM(StatesGroup):
    waiting_name = State()
    waiting_rename = State()
    waiting_invite_username = State()
    waiting_treasury_amount = State()
    waiting_exchange_target = State()
    waiting_exchange_amount = State()
    waiting_bid = State()
    waiting_war_clan = State()


# ── Главное меню кланов ───────────────────────────────────────────────────────

@router.callback_query(F.data == "clans_menu")
async def cb_clans_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    builder = InlineKeyboardBuilder()

    if clan:
        await _show_clan_main(cb, session, user, clan)
        return

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

    # Активная война
    from app.models.clan import ClanWar
    active_war = await session.scalar(
        select(ClanWar).where(
            ClanWar.is_finished == False,
            (ClanWar.clan1_id == clan.id) | (ClanWar.clan2_id == clan.id)
        )
    )

    # Активный аукцион
    active_auction = await clan_service.get_active_auction(session, clan.id)

    builder = InlineKeyboardBuilder()
    if is_owner:
        builder.row(InlineKeyboardButton(text="📨 Пригласить", callback_data="clan_invite"))
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

    war_str = ""
    if active_war:
        war_str = f"\n⚔️ Идёт война!"

    try:
        await cb.message.edit_text(
            f"🏯 <b>{html.escape(clan.name)}</b>"
            f"{'  👑 Владелец' if is_owner else ''}\n\n"
            f"{'─' * 20}\n"
            f"👥 Участников: {len(members)}/{clan.max_members}\n"
            f"💪 Боевая мощь: {fmt_num(clan.combat_power)}\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin"
            f"{war_str}\n\n"
            f"Выбери действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ── Создание клана ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_create")
async def cb_clan_create(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ClanFSM.waiting_name)
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


@router.message(ClanFSM.waiting_name)
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


# ── Поиск клана ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_search:"))
async def cb_clan_search(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    PAGE = 8
    clans = await clan_service.get_top_clans(session, limit=50)
    total = len(clans)
    page_clans = clans[page * PAGE:(page + 1) * PAGE]

    builder = InlineKeyboardBuilder()
    for clan in page_clans:
        members = await clan_service.get_clan_members(session, clan.id)
        builder.row(InlineKeyboardButton(
            text=f"🏯 {html.escape(clan.name)} | 💪{fmt_num(clan.combat_power)} | 👥{len(members)}/5",
            callback_data=f"clan_view:{clan.id}"
        ))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"clan_search:{page-1}"))
    if (page + 1) * PAGE < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"clan_search:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            f"🔍 <b>Все кланы</b> (топ по силе)\n\nНажми на клан чтобы подать заявку:",
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

    builder = InlineKeyboardBuilder()
    if not my_clan and len(members) < clan.max_members:
        # Проверяем нет ли уже запроса
        existing = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.to_user_id == user.id,
                ClanInvite.is_pending == True,
            )
        )
        if not existing:
            builder.row(InlineKeyboardButton(
                text="📨 Подать заявку",
                callback_data=f"clan_request:{clan_id}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text="⏳ Заявка отправлена",
                callback_data="noop_clan"
            ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_search:0"))

    try:
        await cb.message.edit_text(
            f"🏯 <b>{html.escape(clan.name)}</b>\n\n"
            f"👥 Участников: {len(members)}/{clan.max_members}\n"
            f"💪 Боевая мощь: {fmt_num(clan.combat_power)}\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin",
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

    # Уведомляем владельца
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


# ── Приглашение ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_invite")
async def cb_clan_invite(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        await cb.answer("Только владелец может управлять приглашениями", show_alert=True)
        return

    # Входящие заявки
    pending_requests = await session.execute(
        select(ClanInvite).where(
            ClanInvite.clan_id == clan.id,
            ClanInvite.invite_type == "request",
            ClanInvite.is_pending == True,
        )
    )
    requests = pending_requests.scalars().all()

    builder = InlineKeyboardBuilder()

    # Секция заявок
    if requests:
        builder.row(InlineKeyboardButton(
            text=f"📋 Заявки на вступление ({len(requests)})",
            callback_data="noop_clan"
        ))
        for req in requests:
            requester = await session.scalar(
                select(User).where(User.id == req.from_user_id)
            )
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
    await state.set_state(ClanFSM.waiting_invite_username)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_invite"))
    try:
        await cb.message.edit_text(
            "📨 Введите @username игрока которого хотите пригласить:",
            reply_markup=cancel_kb.as_markup(),
        )
    except Exception:
        pass

@router.message(ClanFSM.waiting_invite_username)
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
        builder.row(InlineKeyboardButton(
            text="✅ Принять", callback_data=f"clan_accept:{invite_id}"
        ))
        builder.row(InlineKeyboardButton(
            text="❌ Отклонить", callback_data=f"clan_decline:{invite_id}"
        ))
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

    await message.answer(f"✅ Приглашение отправлено {html.escape(to_user.full_name)}!", parse_mode="HTML")


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
    result = await clan_service.accept_invite(session, invite_id, requester)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(f"✅ {requester.full_name} принят в клан!", show_alert=True)

    from app.bot_instance import get_bot
    bot = get_bot()
    if bot and requester.notifications_enabled:
        try:
            await bot.send_message(
                requester.tg_id,
                f"✅ <b>Ваша заявка одобрена!</b>\n\nВы вступили в клан <b>{html.escape(result['clan'].name)}</b>!",
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
    if bot and requester and requester.notifications_enabled:
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


# ── Казна ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_treasury")
async def cb_clan_treasury(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    await state.set_state(ClanFSM.waiting_treasury_amount)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clans_menu"))
    try:
        await cb.message.edit_text(
            f"🏦 <b>Казна клана {html.escape(clan.name)}</b>\n\n"
            f"В казне: {fmt_num(clan.treasury)} NHCoin\n"
            f"У вас: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"Введите сумму для пополнения:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(ClanFSM.waiting_treasury_amount)
async def msg_treasury_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.deposit_treasury(session, clan, user, amount)
    if result["ok"]:
        await message.answer(
            f"✅ Вы пополнили казну на {fmt_num(amount)} NHCoin!\n"
            f"Казна: {fmt_num(clan.treasury)} NHCoin",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ {result['reason']}")


# ── Магазин клана ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_shop")
async def cb_clan_shop(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in CLAN_SHOP_CATEGORIES.items():
        builder.row(InlineKeyboardButton(
            text=cat_name,
            callback_data=f"clan_shop_cat:{cat_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            f"🛒 <b>Магазин клана {html.escape(clan.name)}</b>\n\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin\n\n"
            f"Выбери категорию:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _show_upgrades_cat(cb: CallbackQuery, clan: Clan):
    from app.constants.clan import CLAN_UPGRADES

    builder = InlineKeyboardBuilder()
    for upgrade in CLAN_UPGRADES:
        can = "✅" if clan.treasury >= upgrade.price else "❌"

        already = False
        if upgrade.upgrade_type == "income" and clan.bonus_income_pct > 0:
            already = True
        elif upgrade.upgrade_type == "ticket" and clan.bonus_ticket_pct > 0:
            already = True
        elif upgrade.upgrade_type == "train" and clan.bonus_train_pct > 0:
            already = True
        elif upgrade.upgrade_type == "slots" and clan.bonus_max_members >= upgrade.max_total:
            already = True

        icon = "🔒" if already else can
        builder.row(InlineKeyboardButton(
            text=f"{icon} {upgrade.name} — {fmt_num(upgrade.price)}",
            callback_data="noop_clan" if already else f"clan_upgrade:{upgrade.upgrade_id}"
        ))

    slots_str = f"+{clan.bonus_max_members}" if clan.bonus_max_members > 0 else "нет"
    bonuses = []
    if clan.bonus_income_pct: bonuses.append(f"💰 Доход +{clan.bonus_income_pct}%")
    if clan.bonus_ticket_pct: bonuses.append(f"🎟 Тикет +{clan.bonus_ticket_pct}%")
    if clan.bonus_train_pct:  bonuses.append(f"🏋 Трен. +{clan.bonus_train_pct}%")
    bonuses_str = "\n".join(bonuses) if bonuses else "нет"

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_shop"))

    try:
        await cb.message.edit_text(
            f"⚙️ <b>Улучшения клана</b>\n\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin\n"
            f"👥 Слоты: {clan.max_members} (доп: {slots_str}, макс +25)\n\n"
            f"Активные бонусы:\n{bonuses_str}\n\n"
            f"Улучшения применяются ко всем участникам:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_shop_cat:"))
async def cb_clan_shop_cat(cb: CallbackQuery, session: AsyncSession, user: User):
    cat_id = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    if cat_id == "upgrades":
        await _show_upgrades_cat(cb, clan)
        return

    cat_name = CLAN_SHOP_CATEGORIES.get(cat_id, cat_id)
    from app.constants.clan import CLAN_SHOP_ITEMS
    items = [i for i in CLAN_SHOP_ITEMS if i.category == cat_id]

    builder = InlineKeyboardBuilder()
    for item in items:
        can = "✅" if clan.treasury >= item.price else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} {item.name} — {fmt_num(item.price)}",
            callback_data=f"clan_buy:{item.item_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_shop"))

    try:
        await cb.message.edit_text(
            f"🛒 <b>{cat_name}</b>\n\n"
            f"🏦 Казна: {fmt_num(clan.treasury)} NHCoin\n\n"
            f"Покупки применяются ко всем участникам клана:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_upgrade:"))
async def cb_clan_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    upgrade_id = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.buy_upgrade(session, clan, user, upgrade_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    upgrade = result["upgrade"]
    await cb.answer(f"✅ {upgrade.name} куплено!", show_alert=True)
    await _show_upgrades_cat(cb, clan)


@router.callback_query(F.data.startswith("clan_buy:"))
async def cb_clan_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    item_id = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    item = CLAN_SHOP_MAP.get(item_id)
    result = await clan_service.buy_clan_shop(session, clan, user, item_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(f"✅ {item.name} куплено!", show_alert=True)
    # Возвращаемся в категорию
    if item:
        cb.data = f"clan_shop_cat:{item.category}"
        await cb_clan_shop_cat(cb, session, user)
    else:
        await cb_clan_shop(cb, session, user)


# ── Аукцион клана ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_auction_info")
async def cb_clan_auction_info(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))
    try:
        await cb.message.edit_text(
            "🏛 <b>Клановый аукцион</b>\n\n"
            "Аукцион можно запустить через магазин клана.\n"
            "Только участники клана могут делать ставки.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_auction:"))
async def cb_clan_auction(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    auction_id = int(cb.data.split(":")[1])
    auction = await session.scalar(select(ClanAuction).where(ClanAuction.id == auction_id))
    if not auction:
        await cb.answer("Аукцион не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    remaining = max(0, int((auction.ends_at - now).total_seconds()))
    h, m = divmod(remaining // 60, 60)

    try:
        reward = json.loads(auction.reward_data) if auction.reward_data else {}
    except Exception:
        reward = {}

    reward_str = f"{reward.get('type', '?')} x{reward.get('amount', '?')}"

    leader = None
    if auction.leader_id:
        leader = await session.scalar(select(User).where(User.id == auction.leader_id))

    builder = InlineKeyboardBuilder()
    if remaining > 0:
        builder.row(InlineKeyboardButton(
            text="💰 Сделать ставку",
            callback_data=f"clan_bid:{auction_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            f"🏛 <b>Клановый аукцион</b>\n\n"
            f"🎁 Приз: {reward_str}\n"
            f"💰 Текущая ставка: {fmt_num(auction.current_bid)} NHCoin\n"
            f"👤 Лидер: {html.escape(leader.full_name) if leader else 'нет'}\n\n"
            f"⏳ До конца: {h}ч {m}м",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_bid:"))
async def cb_clan_bid(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    auction_id = int(cb.data.split(":")[1])
    await state.set_state(ClanFSM.waiting_bid)
    await state.update_data(auction_id=auction_id)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data=f"clan_auction:{auction_id}"
    ))
    try:
        await cb.message.edit_text(
            "💰 Введите размер ставки:",
            reply_markup=cancel_kb.as_markup(),
        )
    except Exception:
        pass


@router.message(ClanFSM.waiting_bid)
async def msg_clan_bid(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    auction_id = data.get("auction_id")

    auction = await session.scalar(
        select(ClanAuction).where(ClanAuction.id == auction_id)
    )
    if not auction:
        await message.answer("❌ Аукцион не найден")
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.bid_auction(session, auction, user, amount)
    if result["ok"]:
        await message.answer(f"✅ Ставка {fmt_num(amount)} NHCoin принята!")
    else:
        await message.answer(f"❌ {result['reason']}")


# ── Война ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_war")
async def cb_clan_war(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan or clan.owner_id != user.id:
        await cb.answer("Только владелец может начать войну", show_alert=True)
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
            "⚔️ <b>Война вооружения</b> — у кого больше вырастет боевая мощь за 6 часов\n\n"
            "💰 <b>Война богатств</b> — у кого будет больше монет в казне за 4 часа\n\n"
            "Выбери тип войны:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_war_type:"))
async def cb_clan_war_type(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    war_type = cb.data.split(":")[1]
    await state.set_state(ClanFSM.waiting_war_clan)
    await state.update_data(war_type=war_type)

    # Показываем список кланов
    clans = await clan_service.get_top_clans(session, limit=20)
    my_clan = await clan_service.get_user_clan(session, user.id)

    builder = InlineKeyboardBuilder()
    for clan in clans:
        if clan.id == my_clan.id:
            continue
        builder.row(InlineKeyboardButton(
            text=f"🏯 {html.escape(clan.name)} | 💪{fmt_num(clan.combat_power)}",
            callback_data=f"clan_war_start:{clan.id}:{war_type}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_war"))

    type_name = "вооружения" if war_type == "power" else "богатств"
    try:
        await cb.message.edit_text(
            f"⚔️ <b>Война {type_name}</b>\n\nВыбери противника:",
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
    h = int((ends_at - datetime.now(timezone.utc)).total_seconds() // 3600)

    await cb.answer(f"⚔️ Война началась! Длится {h} часов.", show_alert=True)

    # Уведомляем владельца вражеского клана
    from app.bot_instance import get_bot
    bot = get_bot()
    enemy_owner = await session.scalar(select(User).where(User.id == target_clan.owner_id))
    if bot and enemy_owner and enemy_owner.notifications_enabled:
        type_name = "вооружения" if war_type == "power" else "богатств"
        try:
            await bot.send_message(
                enemy_owner.tg_id,
                f"⚔️ <b>Война началась!</b>\n\n"
                f"Клан <b>{html.escape(my_clan.name)}</b> объявил войну вашему клану!\n"
                f"Тип: война {type_name}\n"
                f"Длится {h} часов.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb_clans_menu(cb, session, user)


@router.callback_query(F.data.startswith("clan_war_status:"))
async def cb_clan_war_status(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.models.clan import ClanWar
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
        stat_str = (
            f"💪 {html.escape(clan1.name)}: +{fmt_num(diff1)}\n"
            f"💪 {html.escape(clan2.name)}: +{fmt_num(diff2)}"
        )
    else:
        cur1 = clan1.treasury if clan1 else 0
        cur2 = clan2.treasury if clan2 else 0
        diff1 = cur1 - war.clan1_start
        diff2 = cur2 - war.clan2_start
        stat_str = (
            f"🏦 {html.escape(clan1.name)}: +{fmt_num(diff1)}\n"
            f"🏦 {html.escape(clan2.name)}: +{fmt_num(diff2)}"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"clan_war_status:{war_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    type_name = "вооружения" if war.war_type == "power" else "богатств"
    try:
        await cb.message.edit_text(
            f"⚔️ <b>Война {type_name}</b>\n\n"
            f"{stat_str}\n\n"
            f"⏳ До конца: {h}ч {m}м",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ── Обмен ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_exchange")
async def cb_clan_exchange(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    other_members = [m for m in members if m.user_id != user.id]

    if not other_members:
        await cb.answer("В клане нет других участников", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for m in other_members:
        target = await session.scalar(select(User).where(User.id == m.user_id))
        if target:
            builder.row(InlineKeyboardButton(
                text=f"👤 {html.escape(target.full_name)} | 💪{fmt_num(target.combat_power)}",
                callback_data=f"clan_exch_target:{target.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text(
            "🔄 <b>Обмен ресурсами</b>\n\nВыбери участника для обмена:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_target:"))
async def cb_clan_exch_target(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    target_id = int(cb.data.split(":")[1])
    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    await state.update_data(target_id=target_id)

    RESOURCES = [
        ("coins", "💰 NHCoin"),
        ("tickets", "🎟 Тикеты"),
        ("mastery_points", "⭐ Очки мастерства"),
        ("ui_fragments", "🔮 Фрагменты УИ"),
        ("path_points", "🔷 Очки пути"),
        ("squad", "👥 Статисты"),
        ("character", "⭐ Персонаж"),
    ]

    builder = InlineKeyboardBuilder()
    for res_id, res_name in RESOURCES:
        builder.row(InlineKeyboardButton(
            text=res_name,
            callback_data=f"clan_exch_res:{target_id}:{res_id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_exchange"))

    try:
        await cb.message.edit_text(
            f"🔄 Обмен с <b>{html.escape(target.full_name)}</b>\n\nВыбери ресурс:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_exch_res:"))
async def cb_clan_exch_res(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    resource = parts[2]

    await state.set_state(ClanFSM.waiting_exchange_amount)
    await state.update_data(target_id=target_id, resource=resource)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data=f"clan_exch_target:{target_id}"
    ))
    try:
        await cb.message.edit_text(
            f"🔄 Введите количество для передачи:",
            reply_markup=cancel_kb.as_markup(),
        )
    except Exception:
        pass


@router.message(ClanFSM.waiting_exchange_amount)
async def msg_exchange_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    target_id = data.get("target_id")
    resource = data.get("resource")

    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await message.answer("❌ Игрок не найден")
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.exchange_resource(
        session, user, target, resource, amount
    )
    if result["ok"]:
        await message.answer(
            f"✅ Ресурс передан {html.escape(target.full_name)}!",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ {result['reason']}")


# ── Редактирование ────────────────────────────────────────────────────────────

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
            f"✏️ <b>Редактирование клана {html.escape(clan.name)}</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "clan_rename")
async def cb_clan_rename(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ClanFSM.waiting_rename)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_edit"))
    try:
        await cb.message.edit_text(
            "✏️ Введите новое название клана:",
            reply_markup=cancel_kb.as_markup(),
        )
    except Exception:
        pass


@router.message(ClanFSM.waiting_rename)
async def msg_clan_rename(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return
    result = await clan_service.rename_clan(session, clan, user, message.text.strip())
    if result["ok"]:
        await message.answer(f"✅ Клан переименован в <b>{html.escape(clan.name)}</b>!", parse_mode="HTML")
    else:
        await message.answer(f"❌ {result['reason']}")


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
        if bot and target and target.notifications_enabled:
            try:
                await bot.send_message(
                    target.tg_id,
                    f"🚫 Вы были исключены из клана <b>{html.escape(clan.name)}</b>.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await cb_clan_edit(cb, session, user)
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
                text=f"👑 {html.escape(target.full_name)}",
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
            if bot and target and target.notifications_enabled:
                try:
                    await bot.send_message(
                        target.tg_id,
                        f"🗑 Клан <b>{html.escape(clan_name)}</b> был удалён владельцем.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        await cb_clans_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


# ── Покинуть клан ─────────────────────────────────────────────────────────────

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
            # Нужно передать права
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
        await cb_clans_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


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
            f"   💪 {fmt_num(clan.combat_power)} | 👥 {len(members)}/5"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "noop_clan")
async def cb_noop_clan(cb: CallbackQuery):
    await cb.answer()
