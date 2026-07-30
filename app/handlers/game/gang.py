from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.services.game_service import game_service
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_ttl, clamp_enemy_power
from app.services.quest_service import quest_service
from app.utils.truce import truce_button_label
from app.utils.menu_media import send_menu

router = Router()


async def build_gang_menu(session, user, page: int = 0):
    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    if not user.country:
        from app.data.cities import COUNTRIES
        builder = InlineKeyboardBuilder()
        for c in COUNTRIES:
            builder.button(text=f"🌐 {c.label}", callback_data=f"choose_country:{c.code}")
        builder.adjust(2)
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        return (
            "⚔️ <b>Атака — Выбор страны</b>\n\n"
            "Выбери страну — это решение нельзя изменить!\n"
            "В каждой стране свои города (4 типа: 4/8/16/32 района).",
            builder.as_markup(),
            None,
        )

    if not user.gang_city_id:
        from app.data.cities import COUNTRY_BY_CODE
        per_page = 10
        cities = await city_repo.get_available_gang_cities(session, user.country)
        total = len(cities)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        slice_ = cities[page * per_page:(page + 1) * per_page]

        # Города, у которых уже есть король (City.owner_id) — предупреждаем
        # заранее: захват всех районов такого города обернётся битвой за трон.
        king_ids = [c.owner_id for c in slice_ if c.owner_id]
        kings_by_id: dict[int, User] = {}
        if king_ids:
            kings_r = await session.execute(
                select(User.id, User.full_name, User.combat_power).where(User.id.in_(king_ids))
            )
            kings_by_id = {row.id: row for row in kings_r.all()}

        has_kings = False
        builder = InlineKeyboardBuilder()
        type_names = {1: "4р", 2: "8р", 3: "16р", 4: "32р"}
        for city in slice_:
            king = kings_by_id.get(city.owner_id) if city.owner_id else None
            king_str = ""
            if king:
                has_kings = True
                king_str = f" 👑{king.full_name} 💪{fmt_num(king.combat_power)}"
            builder.button(
                text=f"🏙 {city.name} [{type_names.get(city.type_id, '?')}]{king_str}",
                callback_data=f"choose_city:{city.id}"
            )
        builder.adjust(1)

        nav1, nav2 = [], []
        if page >= 5:
            nav1.append(InlineKeyboardButton(text="⏮ -5", callback_data=f"city_page:{page - 5}"))
        if page > 0:
            nav1.append(InlineKeyboardButton(text="◀️", callback_data=f"city_page:{page - 1}"))
        nav1.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav1.append(InlineKeyboardButton(text="▶️", callback_data=f"city_page:{page + 1}"))
        if page + 5 < total_pages:
            nav1.append(InlineKeyboardButton(text="+5 ⏭", callback_data=f"city_page:{page + 5}"))
        builder.row(*nav1)
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        country = COUNTRY_BY_CODE[user.country]
        king_warning = (
            "\n\n👑 У городов с короной уже есть король — захватишь все "
            "районы, и будет битва за трон с ним (можешь проиграть, если "
            "он сильнее). Пока он под 🕊 перемирием, добить последний "
            "район не получится."
            if has_kings else ""
        )
        return (
            f"⚔️ <b>Выбор города — {country.label}</b>\n\n"
            f"Выбери город. После выбора нельзя сменить\n"
            f"пока не завоюешь все районы!\n\n"
            f"🏙 Доступно городов: {total}"
            + king_warning,
            builder.as_markup(),
            country.image,
        )

    from app.data.cities import COUNTRY_BY_CODE
    situation = await game_service.gang_get_situation(session, user)
    if not situation["ok"]:
        return situation["reason"], back_kb("main_menu"), None

    city = situation["city"]
    my_d = situation["my_districts"]
    total_d = situation["total_districts"]
    rivals = situation["rivals"]
    districts = situation["districts"]

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""

    rival_str = ""
    if rivals:
        rival_str = "\n\n👥 <b>Соперники в городе:</b>"
        for r in rivals:
            rival_power = clamp_enemy_power(r['combat_power'], user.combat_power)
            rival_str += f"\n  ⚔️ {r['name']} | 💪 {fmt_num(rival_power)} | 🏘 {r['districts']}р."

    king_str = ""
    if city.owner_id:
        from app.repositories.user_repo import user_repo
        from app.utils.truce import is_truce_active
        reigning_king = await user_repo.get_by_id(session, city.owner_id)
        if reigning_king:
            king_power = clamp_enemy_power(reigning_king.combat_power, user.combat_power)
            truce_str = " 🕊 под перемирием (последний район не забрать)" if is_truce_active(reigning_king) else ""
            king_str = (
                f"\n\n👑 Трон города: <b>{reigning_king.full_name}</b> | 💪 {fmt_num(king_power)}"
                f"\nЗахватишь все районы — будет битва за трон.{truce_str}"
            )

    text = (
        f"⚔️ <b>Атака — Фаза Банды</b>\n\n"
        f"🏙 Город: <b>{city.name}</b>\n"
        f"🏘 Твоих районов: {my_d}/{total_d}\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n"
        f"🎯 Влияние: {fmt_num(user.influence)}"
        + extra_str + cd_str + rival_str + king_str +
        "\n\n⭐ твой | 🔴 соперник | ⚔️ свободен/бот"
    )

    builder = InlineKeyboardBuilder()
    for d in districts:
        if d["is_mine"]:
            builder.button(text=f"⭐#{d['number']}", callback_data="noop")
        elif cd > 0:
            builder.button(text=f"⏳#{d['number']}", callback_data="attack_cd")
        elif d["owner_id"]:
            builder.button(text=f"🔴#{d['number']} 💪{fmt_num(d['power'])}", callback_data=f"gang_pvp:{d['owner_id']}")
        else:
            builder.button(text=f"⚔️#{d['number']} 💪{fmt_num(d['power'])}", callback_data=f"gang_district:{d['id']}")
    builder.adjust(4)

    if cd > 0:
        builder.row(InlineKeyboardButton(text=f"⏳ КД: {fmt_ttl(cd)}", callback_data="attack_cd"))
    builder.row(InlineKeyboardButton(text=truce_button_label(user), callback_data="truce_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return text, builder.as_markup(), COUNTRY_BY_CODE[user.country].image


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("city_page:"))
async def cb_city_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    text, kb, photo = await build_gang_menu(session, user, page=page)
    await send_menu(cb, text, kb, photo)
    await cb.answer()


@router.callback_query(F.data.startswith("choose_country:"))
async def cb_choose_country(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.data.cities import COUNTRY_BY_CODE
    country = cb.data.split(":")[1]
    result = await game_service.choose_country(session, user, country)
    if result["ok"]:
        await cb.answer(f"✅ {COUNTRY_BY_CODE[country].label} выбрана!")
        # Обновляем объект user из БД чтобы country был актуален
        await session.refresh(user)
        from app.handlers.attack import build_attack_menu
        text, kb, photo = await build_attack_menu(session, user)
        await send_menu(cb, text, kb, photo)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data.startswith("choose_city:"))
async def cb_choose_city(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])
    result = await game_service.choose_gang_city(session, user, city_id)
    if result["ok"]:
        await cb.answer(f"✅ {result['city']} выбран!")
        await session.refresh(user)
        from app.handlers.attack import build_attack_menu
        text, kb, photo = await build_attack_menu(session, user)
        await send_menu(cb, text, kb, photo)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data.startswith("gang_district:"))
async def cb_gang_attack_district(cb: CallbackQuery, session: AsyncSession, user: User):
    district_id = int(cb.data.split(":")[1])
    lock_key = cooldown_service.attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.gang_attack_district(session, user, district_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if result.get("promoted"):
        await send_menu(cb, f"🎉 {result['message']}", back_kb("main_menu"))
        return

    if result.get("destroyed"):
        await send_menu(cb, f"💀 <b>{result['message']}</b>", back_kb("main_menu"))
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    if getattr(user, "fame_set_gaprena", False):
        from app.services.fame_service import fame_service
        await fame_service.gain_overcome_stack(user.id)

    extra_left = result.get("extra_attacks_left", 0)
    extra_str = f"\n⚡ Ещё атак без КД: {extra_left}" if extra_left > 0 else ""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Атаковать снова", callback_data="attack"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await quest_service.add_progress(session, user, "attacks")
    if result["win"]:
        await quest_service.add_progress(session, user, "wins")
        from app.utils.region_activity import record
        await record(session, user.id, "attack_gang")
        crit_str = " ⚡<b>КРИТ!</b>" if result.get("is_crit") else ""
        text = (
            f"✅ <b>Победа!{crit_str}</b>\n\n"
            f"Район #{result['district_num']} захвачен!\n"
            f"Твоих районов: {result['my_districts']}/{result['total']}\n"
            f"Районов в городе: {result['city_captured']}/{result['total']}\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🏴 Мощь района #{result['district_num']}: {fmt_num(result['district_power'])}"
            + extra_str
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"Район #{result.get('district_num', '?')} устоял!\n"
            f"Твоих районов: {result['my_districts']}\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🏴 Мощь района #{result.get('district_num', '?')}: {fmt_num(result['district_power'])}"
            + extra_str
        )
    await send_menu(cb, text, builder.as_markup())


@router.callback_query(F.data.startswith("gang_pvp:"))
async def cb_gang_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    import html
    defender_id = int(cb.data.split(":")[1])
    result = await game_service.gang_attack_pvp(session, user, defender_id)

    if result.get("promoted"):
        await send_menu(cb, f"🎉 {result['message']}", back_kb("main_menu"))
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        if result.get("healed"):
            # Район(ы) освобождены самолечением — старая доска с этой кнопкой
            # уже не отражает реальность (соперник исчез), перерисовываем
            # меню атаки, иначе игрок просто тыкает в ту же мёртвую кнопку.
            text, kb, photo = await build_gang_menu(session, user)
            await send_menu(cb, text, kb, photo)
        return

    if getattr(user, "fame_set_gaprena", False):
        from app.services.fame_service import fame_service
        await fame_service.gain_overcome_stack(user.id)

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}\n\n"
            f"+1 район получен!"
        )
    else:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    await send_menu(cb, text, back_kb("attack"))