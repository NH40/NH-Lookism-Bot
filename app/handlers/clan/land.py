from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.clan import clan_service
from app.utils.formatters import fmt_num, progress_bar
from app.config.game_balance import (
    CLAN_LAND_MAX_LEVEL,
    CLAN_LAND_UPGRADE_COST,
    CLAN_LAND_SLOTS,
    CLAN_LAND_BUILDINGS,
)

router = Router()


def _split_name(cfg: dict) -> tuple[str, str]:
    """cfg['name'] выглядит как '🏷 Скидка в магазине клана' — режем на (эмодзи, текст)."""
    emoji, _, rest = cfg["name"].partition(" ")
    return emoji, rest


@router.callback_query(F.data == "clan_land")
async def cb_clan_land(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    rank = await clan_service.get_member_rank(session, clan.id, user.id)
    can_manage = rank in ("owner", "deputy")

    counts = await clan_service.get_building_counts(session, clan.id)
    slots_used = await clan_service.get_slots_used(session, clan.id)
    total_slots = CLAN_LAND_SLOTS.get(clan.land_level, 0)

    lines = [
        "🏰 <b>Клановые земли</b>\n",
        f"📊 Уровень земли: <b>{clan.land_level}/{CLAN_LAND_MAX_LEVEL}</b>",
        f"🏗 Слоты {progress_bar(slots_used, max(total_slots, 1))} <b>{slots_used}/{total_slots}</b>",
        f"🏦 Казна: <b>{fmt_num(clan.treasury)}</b> NHCoin",
        "",
        "━━━ 🏗 Здания ━━━",
        "<i>Нажми на здание, чтобы построить, снести или посмотреть бонус</i>",
    ]

    builder = InlineKeyboardBuilder()
    for btype, cfg in CLAN_LAND_BUILDINGS.items():
        emoji, _ = _split_name(cfg)
        count = counts.get(btype, 0)
        max_count = cfg.get("max_count")
        cap_str = f"/{max_count}" if max_count is not None else ""
        builder.button(
            text=f"{emoji} {count}{cap_str}",
            callback_data=f"clan_land_detail:{btype}",
        )
    builder.adjust(3)

    if can_manage and clan.land_level < CLAN_LAND_MAX_LEVEL:
        next_cost = CLAN_LAND_UPGRADE_COST[clan.land_level + 1]
        builder.row(InlineKeyboardButton(
            text=f"⬆️ Улучшить землю до Ур.{clan.land_level + 1} ({next_cost:,})",
            callback_data="clan_land_upgrade",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("clan_land_detail:"))
async def cb_clan_land_detail(cb: CallbackQuery, session: AsyncSession, user: User):
    building_type = cb.data.split(":")[1]
    cfg = CLAN_LAND_BUILDINGS.get(building_type)
    if not cfg:
        await cb.answer("Здание не найдено", show_alert=True)
        return

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    rank = await clan_service.get_member_rank(session, clan.id, user.id)
    can_manage = rank in ("owner", "deputy")

    counts = await clan_service.get_building_counts(session, clan.id)
    slots_used = await clan_service.get_slots_used(session, clan.id)
    total_slots = CLAN_LAND_SLOTS.get(clan.land_level, 0)

    emoji, label = _split_name(cfg)
    count = counts.get(building_type, 0)
    max_count = cfg.get("max_count")
    cap_str = f"/{max_count}" if max_count is not None else ""
    unit_str = "%" if cfg["unit"] == "%" else " ур."
    bonus_total = count * cfg["bonus_per_unit"]
    at_cap = max_count is not None and count >= max_count
    refund = cfg["cost"] // 2

    lines = [
        f"{emoji} <b>{label}</b>\n",
        f"📦 Построено: <b>{count}{cap_str}</b>",
        f"📈 Текущий бонус: <b>+{bonus_total}{unit_str}</b>",
        f"➕ За одно здание: <b>+{cfg['bonus_per_unit']}{unit_str}</b>",
        "",
        f"🏗 Слоты земли: {slots_used}/{total_slots}",
        f"🏦 Казна клана: {fmt_num(clan.treasury)} NHCoin",
    ]

    builder = InlineKeyboardBuilder()

    if not can_manage:
        lines.append("\n<i>Строить и сносить может только владелец или заместитель</i>")
    else:
        if at_cap:
            lines.append(f"\n🔒 Достигнут лимит зданий этого типа ({max_count})")
        elif slots_used >= total_slots:
            lines.append("\n🔒 Нет свободных слотов — улучшите землю")
        else:
            can_afford = "✅" if clan.treasury >= cfg["cost"] else "❌"
            builder.row(InlineKeyboardButton(
                text=f"{can_afford} 🏗 Построить — {cfg['cost']:,} NHCoin",
                callback_data=f"clan_land_build:{building_type}",
            ))

        if count > 0:
            builder.row(InlineKeyboardButton(
                text=f"🗑 Снести (вернём {refund:,} NHCoin)",
                callback_data=f"clan_land_demolish:{building_type}",
            ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_land"))

    text = "\n".join(lines)
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("clan_land_build:"))
async def cb_clan_land_build(cb: CallbackQuery, session: AsyncSession, user: User):
    building_type = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.buy_land_building(session, clan, user, building_type)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    await cb.answer(f"✅ Построено: {result['name']}!", show_alert=True)
    await cb_clan_land_detail(cb, session, user)


@router.callback_query(F.data.startswith("clan_land_demolish:"))
async def cb_clan_land_demolish(cb: CallbackQuery, session: AsyncSession, user: User):
    building_type = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.demolish_land_building(session, clan, user, building_type)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    await cb.answer(f"🗑 Снесено: {result['name']}! Возвращено {result['refund']:,} NHCoin", show_alert=True)
    await cb_clan_land_detail(cb, session, user)


@router.callback_query(F.data == "clan_land_upgrade")
async def cb_clan_land_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.buy_land_upgrade(session, clan, user)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    await cb.answer(
        f"✅ Земля улучшена до уровня {result['new_level']}!\n🏗 Слотов: {result['slots']}",
        show_alert=True,
    )
    await cb_clan_land(cb, session, user)
