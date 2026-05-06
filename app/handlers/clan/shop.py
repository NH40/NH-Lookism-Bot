import html
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.clan import Clan
from app.services.clan import clan_service
from app.constants.clan import CLAN_SHOP_ITEMS, CLAN_SHOP_MAP, CLAN_SHOP_CATEGORIES, CLAN_UPGRADES
from app.utils.formatters import fmt_num

router = Router()


@router.callback_query(F.data == "clan_shop")
async def cb_clan_shop(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in CLAN_SHOP_CATEGORIES.items():
        builder.row(InlineKeyboardButton(text=cat_name, callback_data=f"clan_shop_cat:{cat_id}"))
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


@router.callback_query(F.data.startswith("clan_shop_cat:"))
async def cb_clan_shop_cat(cb: CallbackQuery, session: AsyncSession, user: User):
    cat_id = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    if cat_id == "upgrades":
        await _show_upgrades(cb, clan)
        return

    cat_name = CLAN_SHOP_CATEGORIES.get(cat_id, cat_id)
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


async def _show_upgrades(cb: CallbackQuery, clan: Clan):
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


@router.callback_query(F.data.startswith("clan_buy:"))
async def cb_clan_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    item_id = cb.data.split(":")[1]
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    item = CLAN_SHOP_MAP.get(item_id)
    if not item:
        await cb.answer("Товар не найден", show_alert=True)
        return

    result = await clan_service.buy_clan_shop(session, clan, user, item_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(f"✅ {item.name} куплено для всего клана!", show_alert=True)

    # Возвращаемся в категорию
    cb.data = f"clan_shop_cat:{item.category}"
    await cb_clan_shop_cat(cb, session, user)


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
    await _show_upgrades(cb, clan)