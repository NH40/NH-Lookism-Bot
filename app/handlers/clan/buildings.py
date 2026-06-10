import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
from app.config.game_balance import (
    CLAN_REGION_BUILDINGS,
    CLAN_REGION_BUILDING_MAX_LEVEL,
    CLAN_AP_INCOME_BONUS, CLAN_AP_INCOME_MAX, CLAN_AP_INCOME_COST,
    CLAN_AP_TRAIN_BONUS, CLAN_AP_TRAIN_MAX, CLAN_AP_TRAIN_COST,
    CLAN_AP_TICKET_BONUS, CLAN_AP_TICKET_MAX, CLAN_AP_TICKET_COST,
)

router = Router()


class BuildingsFSM(StatesGroup):
    waiting_ap_amount = State()


# ── Меню зданий региона ───────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_region_buildings")
async def cb_region_buildings(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    region = await clan_service.get_clan_region(session, clan.id)
    if not region:
        await cb.answer("Ваш клан не владеет регионом", show_alert=True)
        return

    from sqlalchemy import select
    from app.models.clan import ClanMember
    member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    can_manage = member and member.rank in ("owner", "deputy")

    buildings = await clan_service.get_clan_buildings(session, clan.id)
    bld_by_type = {b.building_type: b for b in buildings}
    base_income = clan_service.calc_total_income_per_member(buildings)

    # Бонусы владельца клана для умножения дохода зданий
    from sqlalchemy import select as sa_select
    from app.models.user import User as UserModel
    owner = await session.scalar(sa_select(UserModel).where(UserModel.id == clan.owner_id))
    owner_bonus = 0
    if owner:
        owner_bonus = (
            (owner.income_bonus_percent or 0)
            + (owner.prestige_income_bonus or 0)
            + (owner.clan_income_bonus or 0)
            + (owner.clan_donat_income_bonus or 0)
            + (owner.region_income_pct or 0)
            + (owner.region_income_building_pct or 0)
        )
    effective_income = max(0, int(base_income * (1 + owner_bonus / 100)))

    owner_bonus_str = f" (×{1 + owner_bonus / 100:.2f} бонус владельца)" if owner_bonus else ""

    lines = [
        f"🏗 <b>Здания региона {region.emoji} {region.name}</b>\n",
        f"🎯 Казна ОА: <b>{clan.treasury_ap}</b>   |   Мои ОА: <b>{user.activity_points}</b>\n",
        f"💰 Итого доход: <b>{fmt_num(effective_income)}/мин</b> каждому участнику{owner_bonus_str}\n",
        "─" * 20,
    ]

    builder = InlineKeyboardBuilder()

    for btype, cfg in CLAN_REGION_BUILDINGS.items():
        b = bld_by_type.get(btype)
        cur_level = b.level if b else 0
        cur_base = cfg["income_per_level"][cur_level] if cur_level > 0 else 0
        next_level = cur_level + 1

        if cur_level == 0:
            level_str = "не построено"
            income_str = ""
        else:
            cur_effective = max(0, int(cur_base * (1 + owner_bonus / 100)))
            level_str = f"Ур.{cur_level}/{CLAN_REGION_BUILDING_MAX_LEVEL}"
            income_str = f"  💰 +{fmt_num(cur_effective)}/мин"

        if next_level <= CLAN_REGION_BUILDING_MAX_LEVEL:
            next_cost = cfg["ap_cost_per_level"][next_level]
            next_base = cfg["income_per_level"][next_level]
            next_effective = max(0, int(next_base * (1 + owner_bonus / 100)))
            action_str = f"→ Ур.{next_level}: {next_cost} ОА (+{fmt_num(next_effective)}/мин)"
        else:
            action_str = "✅ Макс. уровень"

        lines.append(f"\n{cfg['name']}  [{level_str}]{income_str}\n  {action_str}")

        if can_manage and next_level <= CLAN_REGION_BUILDING_MAX_LEVEL:
            builder.row(InlineKeyboardButton(
                text=f"{'🔼 Улучшить' if cur_level > 0 else '🏗 Построить'} {cfg['name']}",
                callback_data=f"clan_build_upgrade:{btype}",
            ))

    builder.row(InlineKeyboardButton(text="⬆️ AP-улучшения клана", callback_data="clan_ap_upgrades"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")


# ── Покупка / улучшение здания ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clan_build_upgrade:"))
async def cb_build_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    building_type = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    region = await clan_service.get_clan_region(session, clan.id)
    if not region:
        await cb.answer("Ваш клан не владеет регионом", show_alert=True)
        return

    from sqlalchemy import select
    from app.models.clan import ClanMember
    member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    if not member or member.rank not in ("owner", "deputy"):
        await cb.answer("Только владелец или заместитель может строить здания", show_alert=True)
        return

    result = await clan_service.buy_or_upgrade_building(session, clan, user, building_type)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    await cb.answer(
        f"✅ {result['name']} → Ур.{result['new_level']}\n"
        f"+{fmt_num(result['income_per_member'])}/мин каждому!",
        show_alert=True,
    )
    await cb_region_buildings(cb, session, user)


# ── Меню AP-улучшений клана ───────────────────────────────────────────────────

@router.callback_query(F.data == "clan_ap_upgrades")
async def cb_ap_upgrades(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    from sqlalchemy import select
    from app.models.clan import ClanMember
    member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    can_manage = member and member.rank in ("owner", "deputy")

    income_circles = getattr(clan, "ap_income_circles", 0)
    train_circles = getattr(clan, "ap_train_circles", 0)
    ticket_circles = getattr(clan, "ap_ticket_circles", 0)
    income_bonus = income_circles * CLAN_AP_INCOME_BONUS
    train_bonus = train_circles * CLAN_AP_TRAIN_BONUS
    ticket_bonus = ticket_circles * CLAN_AP_TICKET_BONUS

    income_next = f"→ +{CLAN_AP_INCOME_BONUS}% (стоит {CLAN_AP_INCOME_COST} ОА)" if income_circles < CLAN_AP_INCOME_MAX else "✅ Максимум"
    train_next = f"→ +{CLAN_AP_TRAIN_BONUS}% (стоит {CLAN_AP_TRAIN_COST} ОА)" if train_circles < CLAN_AP_TRAIN_MAX else "✅ Максимум"
    ticket_next = f"→ +{CLAN_AP_TICKET_BONUS}% (стоит {CLAN_AP_TICKET_COST} ОА)" if ticket_circles < CLAN_AP_TICKET_MAX else "✅ Максимум"

    text = (
        f"⬆️ <b>AP-улучшения клана {html.escape(clan.name)}</b>\n\n"
        f"🎯 Казна ОА: <b>{clan.treasury_ap}</b>\n\n"
        f"💰 <b>Бонус к доходу</b>  [{income_circles}/{CLAN_AP_INCOME_MAX}]\n"
        f"  Текущий: +{income_bonus}%\n"
        f"  {income_next}\n\n"
        f"🏋 <b>Бонус к тренировкам</b>  [{train_circles}/{CLAN_AP_TRAIN_MAX}]\n"
        f"  Текущий: +{train_bonus}%\n"
        f"  {train_next}\n\n"
        f"🎟 <b>Бонус шанса тикета</b>  [{ticket_circles}/{CLAN_AP_TICKET_MAX}]\n"
        f"  Текущий: +{ticket_bonus}%\n"
        f"  {ticket_next}"
    )

    builder = InlineKeyboardBuilder()
    if can_manage:
        if income_circles < CLAN_AP_INCOME_MAX:
            builder.row(InlineKeyboardButton(
                text=f"💰 Купить бонус к доходу +{CLAN_AP_INCOME_BONUS}% ({CLAN_AP_INCOME_COST} ОА)",
                callback_data="clan_ap_buy:income",
            ))
        if train_circles < CLAN_AP_TRAIN_MAX:
            builder.row(InlineKeyboardButton(
                text=f"🏋 Купить бонус к тренировкам +{CLAN_AP_TRAIN_BONUS}% ({CLAN_AP_TRAIN_COST} ОА)",
                callback_data="clan_ap_buy:train",
            ))
        if ticket_circles < CLAN_AP_TICKET_MAX:
            builder.row(InlineKeyboardButton(
                text=f"🎟 Купить бонус шанса тикета +{CLAN_AP_TICKET_BONUS}% ({CLAN_AP_TICKET_COST} ОА)",
                callback_data="clan_ap_buy:ticket",
            ))
    builder.row(InlineKeyboardButton(text="◀️ Здания", callback_data="clan_region_buildings"))

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("clan_ap_buy:"))
async def cb_ap_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    upgrade_type = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    from sqlalchemy import select
    from app.models.clan import ClanMember
    member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    if not member or member.rank not in ("owner", "deputy"):
        await cb.answer("Только владелец или заместитель может покупать улучшения", show_alert=True)
        return

    result = await clan_service.buy_ap_upgrade(session, clan, user, upgrade_type)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    labels = {
        "income": f"+{CLAN_AP_INCOME_BONUS}% к доходу",
        "train": f"+{CLAN_AP_TRAIN_BONUS}% к тренировкам",
        "ticket": f"+{CLAN_AP_TICKET_BONUS}% шанс тикета",
    }
    await cb.answer(f"✅ Улучшение куплено: {labels.get(upgrade_type, upgrade_type)}!", show_alert=True)
    await cb_ap_upgrades(cb, session, user)


# ── Депозит ОА в казну ────────────────────────────────────────────────────────

@router.callback_query(F.data == "clan_deposit_ap")
async def cb_deposit_ap_menu(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    await state.set_state(BuildingsFSM.waiting_ap_amount)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="clan_treasury"))

    try:
        await cb.message.edit_text(
            f"🎯 <b>Пополнить казну ОА — {html.escape(clan.name)}</b>\n\n"
            f"В казне: <b>{clan.treasury_ap} ОА</b>\n"
            f"У вас: <b>{user.activity_points} ОА</b>\n\n"
            f"Введите количество очков активности для взноса (мин. 10):",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(BuildingsFSM.waiting_ap_amount)
async def msg_ap_deposit_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    from app.services.cooldown_service import cooldown_service
    await state.clear()

    lock_key = f"ap_deposit:{user.id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("❌ Подожди...")
        return

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите целое число")
        return

    result = await clan_service.deposit_ap(session, clan, user, amount)
    if result["ok"]:
        await message.answer(
            f"✅ Вы пополнили казну на <b>{amount} ОА</b>!\n"
            f"🎯 В казне: {clan.treasury_ap} ОА",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ {result['reason']}")
