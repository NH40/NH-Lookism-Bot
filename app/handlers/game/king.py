from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.city import District
from app.services.game_service import game_service
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_ttl
import html

router = Router()


async def build_king_menu(session, user):
    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    cities = await city_repo.get_available_king_cities(session, user.sector or "Н")

    my_city_ids_r = await session.execute(
        select(District.city_id).where(
            District.owner_id == user.id,
            District.is_captured == True,
        ).distinct()
    )
    my_city_ids = set(my_city_ids_r.scalars().all())

    builder = InlineKeyboardBuilder()
    type_counts: dict[int, int] = {}

    for city in cities:
        type_id = city.type_id or 1
        if type_counts.get(type_id, 0) >= 3:
            continue

        my_in_city = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user.id,
                District.city_id == city.id,
                District.is_captured == True,
            )
        ) or 0

        not_mine = await session.scalar(
            select(func.count(District.id)).where(
                District.city_id == city.id,
                District.is_captured == True,
                District.owner_id != user.id,
            )
        ) or 0

        free_count = await session.scalar(
            select(func.count(District.id)).where(
                District.city_id == city.id,
                District.is_captured == False,
                District.owner_id == None,
            )
        ) or 0

        if free_count == 0 and not_mine == 0:
            continue

        type_counts[type_id] = type_counts.get(type_id, 0) + 1

        dominant_id = await game_service._get_city_dominant_player(session, city.id, user.id)
        if dominant_id:
            defender = await user_repo.get_by_id(session, dominant_id)
            def_power = int(defender.combat_power) if defender else 0
            def_str = f"👤{fmt_num(def_power)}"
        else:
            from app.data.cities import KING_DISTRICT_BASE_POWER
            bot_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
            def_str = f"🤖{fmt_num(bot_power)}"

        my_str = f"[моих:{my_in_city}] " if my_in_city > 0 else ""
        size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(type_id, "🏙")

        builder.button(
            text=f"{size_emoji} {city.name} {my_str}{city.captured_districts}/{city.total_districts}р | {def_str}",
            callback_data=f"king_attack:{city.id}"
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🤖 Боты-короли", callback_data="king_bots_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""

    text = (
        f"⚔️ <b>Атака — Фаза Короля</b>\n\n"
        f"Городов с районами: {len(my_city_ids)}/10\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}"
        + extra_str + cd_str +
        f"\n\nВыбери город для атаки:"
    )
    return text, builder.as_markup()


@router.callback_query(F.data.startswith("king_attack:"))
async def cb_king_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])

    from sqlalchemy import func as sa_func
    free_count = await session.scalar(
        select(sa_func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == False,
            District.owner_id == None,
        )
    ) or 0
    not_mine = await session.scalar(
        select(sa_func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == True,
            District.owner_id != user.id,
        )
    ) or 0

    if free_count == 0 and not_mine == 0:
        await cb.answer("В этом городе нечего атаковать — все районы твои!", show_alert=True)
        return

    result = await game_service.king_attack(session, user, city_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {html.escape(result['message'])}",
            reply_markup=back_kb("main_menu"), parse_mode="HTML"
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    is_pvp = result.get("defender_name") is not None

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Атаковать снова", callback_data="attack"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))

    if is_pvp:
        if result["win"]:
            taken = result.get("districts_taken", 0)
            text = (
                f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
                f"Противник: <b>{html.escape(result['defender_name'])}</b>\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n"
                f"Забрано районов: +{taken}\n"
                f"Моих в городе: {result.get('my_in_city', 0)}\n\n"
                f"Городов с районами: {result.get('cities_count', 0)}/10\n\n"
                f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
                f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
            )
        else:
            text = (
                f"❌ <b>Поражение в PvP!</b>\n\n"
                f"Противник: <b>{html.escape(result['defender_name'])}</b>\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n\n"
                f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
                f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
            )
    else:
        if result["win"]:
            text = (
                f"✅ <b>Победа!{crit_str}</b>\n\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n"
                f"Захвачено районов: <b>+{result.get('districts_gained', 0)}</b>\n"
                f"Моих районов в городе: {result.get('my_in_city', 0)}\n"
                f"Всего в городе: {result.get('city_captured', 0)}/{result.get('city_total', 0)}\n\n"
                f"Городов с районами: {result['cities_count']}/10\n\n"
                f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
                f"🤖 Мощь противника: {fmt_num(result['bot_power'])}"
            )
        else:
            text = (
                f"❌ <b>Поражение!</b>\n\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n"
                f"Районов в городе: {result.get('city_captured', 0)}/{result.get('city_total', 0)}\n\n"
                f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
                f"🤖 Мощь противника: {fmt_num(result['bot_power'])}"
            )

    await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")