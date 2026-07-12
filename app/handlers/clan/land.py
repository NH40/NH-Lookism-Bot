from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
from app.config.game_balance import (
    CLAN_LAND_MAX_LEVEL,
    CLAN_LAND_UPGRADE_COST,
    CLAN_LAND_SLOTS,
    CLAN_LAND_BUILDINGS,
)

router = Router()


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
        f"🏰 <b>Клановые земли</b>\n",
        f"📊 Уровень земли: <b>{clan.land_level}/{CLAN_LAND_MAX_LEVEL}</b>",
        f"🏗 Слоты зданий: <b>{slots_used}/{total_slots}</b>",
        f"🏦 Казна: <b>{fmt_num(clan.treasury)}</b> NHCoin\n",
        "─" * 20,
    ]

    builder = InlineKeyboardBuilder()

    for btype, cfg in CLAN_LAND_BUILDINGS.items():
        count = counts.get(btype, 0)
        max_count = cfg.get("max_count")
        bonus_total = count * cfg["bonus_per_unit"]
        cap_str = f"/{max_count}" if max_count is not None else ""
        lines.append(
            f"\n{cfg['name']}  [{count}{cap_str}]\n"
            f"  +{bonus_total}{'%' if cfg['unit'] == '%' else ' ур.'} "
            f"(след. {cfg['cost']:,} NHCoin)"
        )
        at_cap = max_count is not None and count >= max_count
        if can_manage and not at_cap and slots_used < total_slots:
            builder.row(InlineKeyboardButton(
                text=f"🏗 Построить {cfg['name']} ({cfg['cost']:,})",
                callback_data=f"clan_land_build:{btype}",
            ))

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
    await cb_clan_land(cb, session, user)


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
