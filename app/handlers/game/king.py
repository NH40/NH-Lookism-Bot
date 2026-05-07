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
            can = "✅" if user.combat_power >= def_power else "❌"
            def_str = f"👤 {can} {fmt_num(def_power)}"
        else:
            from app.data.cities import KING_DISTRICT_BASE_POWER
            bot_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
            can = "✅" if user.combat_power >= bot_power else "❌"
            def_str = f"🤖 {can} {fmt_num(bot_power)}"

        my_str = f"[моих:{my_in_city}] " if my_in_city > 0 else ""
        size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(type_id, "🏙")

        # Прогресс бар города
        total = city.total_districts
        captured = city.captured_districts
        pct = int(captured / total * 100) if total > 0 else 0
        bar_filled = int(pct / 10)
        bar = "🟩" * bar_filled + "⬛" * (10 - bar_filled)

        builder.row(InlineKeyboardButton(
            text=f"{size_emoji} {city.name} {my_str}| {def_str}",
            callback_data=f"king_city_info:{city.id}"
        ))

    builder.adjust(1)
    cities_count = len(my_city_ids)
    if cities_count >= 9:
        builder.row(InlineKeyboardButton(
            text=f"⚠️ {cities_count}/10 — последний город не через ботов!",
            callback_data="king_bots_menu"
        ))
    else:
        builder.row(InlineKeyboardButton(text="🤖 Боты-короли", callback_data="king_bots_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""

    nine_hint = "\n\n⚠️ <b>Последний город захвати через список городов выше — не через ботов!</b>" if cities_count >= 9 else ""

    text = (
        f"⚔️ <b>Атака — Фаза Короля</b>\n\n"
        f"{'─' * 20}\n"
        f"🏙 Городов с районами: <b>{cities_count}/10</b>\n"
        f"💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>"
        + extra_str + cd_str +
        f"\n{'─' * 20}\n\n"
        f"Выбери город для атаки:"
        + nine_hint
    )
    return text, builder.as_markup()


@router.callback_query(F.data.startswith("king_city_info:"))
async def cb_king_city_info(cb: CallbackQuery, session: AsyncSession, user: User):
    """Подробная информация о городе перед атакой — как у ботов."""
    city_id = int(cb.data.split(":")[1])

    from app.models.city import City
    city_result = await session.execute(
        select(District.city_id).where(District.city_id == city_id).limit(1)
    )

    from app.repositories.city_repo import city_repo as cr
    city = await cr.get_city(session, city_id)
    if not city:
        await cb.answer("Город не найден", show_alert=True)
        return

    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)
    attack_on_cd = cd > 0

    my_in_city = await session.scalar(
        select(func.count(District.id)).where(
            District.owner_id == user.id,
            District.city_id == city_id,
            District.is_captured == True,
        )
    ) or 0

    free_count = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == False,
            District.owner_id == None,
        )
    ) or 0

    not_mine = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == True,
            District.owner_id != user.id,
        )
    ) or 0

    if free_count == 0 and not_mine == 0:
        await cb.answer("Все районы твои — нечего атаковать!", show_alert=True)
        return

    # Определяем противника
    dominant_id = await game_service._get_city_dominant_player(session, city_id, user.id)
    is_pvp = False
    defender_name = None
    if dominant_id:
        defender = await user_repo.get_by_id(session, dominant_id)
        if defender and defender.phase == "king":
            is_pvp = True
            defender_name = defender.full_name
            enemy_power = int(defender.combat_power)
        else:
            enemy_power = int(defender.combat_power * 0.7) if defender else 0
    else:
        from app.data.cities import KING_DISTRICT_BASE_POWER
        from app.models.building import UserBuilding
        buildings_count = await session.scalar(
            select(func.count(UserBuilding.id)).where(
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        ) or 0
        if buildings_count > 0:
            enemy_power = int(buildings_count * 50 * city.district_power_multiplier * 0.7)
        else:
            enemy_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
        enemy_power = max(100, enemy_power)

    can_win = user.combat_power >= enemy_power
    power_diff = user.combat_power - enemy_power
    power_str = f"+{fmt_num(power_diff)}" if power_diff >= 0 else fmt_num(power_diff)

    # Прогресс бар
    total = city.total_districts
    captured = city.captured_districts
    pct = int(captured / total * 100) if total > 0 else 0
    bar_filled = int(pct / 10)
    progress_bar = "🟩" * bar_filled + "⬛" * (10 - bar_filled)

    size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(city.type_id or 1, "🏙")

    builder = InlineKeyboardBuilder()

    if attack_on_cd:
        builder.row(InlineKeyboardButton(
            text=f"⏳ КД: {fmt_ttl(cd)}",
            callback_data="attack_cd"
        ))
    elif not can_win:
        builder.row(InlineKeyboardButton(
            text=f"❌ Недостаточно мощи (нужно {fmt_num(enemy_power)})",
            callback_data="noop_king"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="⚔️ Атаковать!",
            callback_data=f"king_attack:{city_id}"
        ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"king_city_info:{city_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="attack"
    ))

    enemy_str = f"👤 PvP: {html.escape(defender_name)}" if is_pvp else "🤖 Бот"
    status_str = f"{'✅ Можешь победить' if can_win else '❌ Слишком слабый'} ({power_str})"

    try:
        await cb.message.edit_text(
            f"{size_emoji} <b>{html.escape(city.name)}</b>\n\n"
            f"{'─' * 20}\n"
            f"💪 Мощь противника: <b>{fmt_num(enemy_power)}</b> {enemy_str}\n"
            f"💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>\n"
            f"📈 Разница: {power_str}\n\n"
            f"{'─' * 20}\n"
            f"🏘 Прогресс города:\n"
            f"{progress_bar} {pct}%\n"
            f"Всего районов: {captured}/{total}\n"
            f"Моих районов: <b>{my_in_city}</b>\n"
            f"Свободных: {free_count} | Чужих: {not_mine}\n\n"
            f"{'─' * 20}\n"
            f"{status_str}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("king_attack:"))
async def cb_king_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])

    free_count = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == False,
            District.owner_id == None,
        )
    ) or 0
    not_mine = await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id,
            District.is_captured == True,
            District.owner_id != user.id,
        )
    ) or 0

    if free_count == 0 and not_mine == 0:
        await cb.answer("Все районы твои — нечего атаковать!", show_alert=True)
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

    from app.services.quest_service import quest_service
    await quest_service.add_progress(session, user, "attacks")
    if result["win"]:
        await quest_service.add_progress(session, user, "wins")

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    is_pvp = result.get("defender_name") is not None

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚔️ Атаковать снова", callback_data=f"king_city_info:{city_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ К городам", callback_data="attack"
    ))

    if is_pvp:
        if result["win"]:
            taken = result.get("districts_taken", 0)
            text = (
                f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
                f"{'─' * 20}\n"
                f"Противник: <b>{html.escape(result['defender_name'])}</b>\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n\n"
                f"🏘 Забрано районов: <b>+{taken}</b>\n"
                f"Моих в городе: {result.get('my_in_city', 0)}\n"
                f"Городов с районами: {result.get('cities_count', 0)}/10\n\n"
                f"{'─' * 20}\n"
                f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
                f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
            )
        else:
            text = (
                f"❌ <b>Поражение в PvP!</b>\n\n"
                f"{'─' * 20}\n"
                f"Противник: <b>{html.escape(result['defender_name'])}</b>\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n\n"
                f"{'─' * 20}\n"
                f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
                f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
            )
    else:
        if result["win"]:
            text = (
                f"✅ <b>Победа!{crit_str}</b>\n\n"
                f"{'─' * 20}\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n\n"
                f"🏘 Захвачено районов: <b>+{result.get('districts_gained', 0)}</b>\n"
                f"Моих в городе: {result.get('my_in_city', 0)}\n"
                f"Всего в городе: {result.get('city_captured', 0)}/{result.get('city_total', 0)}\n"
                f"Городов с районами: {result['cities_count']}/10\n\n"
                f"{'─' * 20}\n"
                f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
                f"🤖 Мощь противника: {fmt_num(result['bot_power'])}"
            )
        else:
            text = (
                f"❌ <b>Поражение!</b>\n\n"
                f"{'─' * 20}\n"
                f"Город: <b>{html.escape(result['city'])}</b>\n\n"
                f"Районов в городе: {result.get('city_captured', 0)}/{result.get('city_total', 0)}\n\n"
                f"{'─' * 20}\n"
                f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
                f"🤖 Мощь противника: {fmt_num(result['bot_power'])}"
            )

    try:
        await cb.message.edit_text(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "noop_king")
async def cb_noop_king(cb: CallbackQuery):
    await cb.answer()