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
from app.utils.formatters import fmt_num, fmt_ttl
from app.services.quest_service import quest_service
from app.utils.truce import truce_button_label

router = Router()


async def build_gang_menu(session, user, page: int = 0):
    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    if not user.sector:
        builder = InlineKeyboardBuilder()
        for s in ["Н", "Х", "Ч", "Б", "М", "Ж"]:
            builder.button(text=f"🌐 Сектор {s}", callback_data=f"choose_sector:{s}")
        builder.adjust(3)
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        return (
            "⚔️ <b>Атака — Выбор сектора</b>\n\n"
            "Выбери сектор — это решение нельзя изменить!\n"
            "В каждом секторе 50 городов (5 типов × 10 штук).",
            builder.as_markup()
        )

    if not user.gang_city_id:
        per_page = 10
        cities = await city_repo.get_available_gang_cities(session, user.sector)
        total = len(cities)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        slice_ = cities[page * per_page:(page + 1) * per_page]

        builder = InlineKeyboardBuilder()
        type_names = {1: "4р", 2: "8р", 3: "16р", 4: "32р", 5: "64р"}
        for city in slice_:
            builder.button(
                text=f"🏙 {city.name} [{type_names.get(city.type_id, '?')}]",
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
        return (
            f"⚔️ <b>Выбор города — Сектор {user.sector}</b>\n\n"
            f"Выбери город. После выбора нельзя сменить\n"
            f"пока не завоюешь все районы!\n\n"
            f"🏙 Доступно городов: {total}",
            builder.as_markup()
        )

    situation = await game_service.gang_get_situation(session, user)
    if not situation["ok"]:
        return situation["reason"], back_kb("main_menu")

    city = situation["city"]
    my_d = situation["my_districts"]
    total_d = situation["total_districts"]
    bot_power = situation["bot_district_power"]
    rivals = situation["rivals"]
    next_bot = situation["next_bot_district"]

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""

    rival_str = ""
    if rivals:
        rival_str = "\n\n👥 <b>Соперники в городе:</b>"
        for r in rivals:
            rival_str += f"\n  ⚔️ {r['name']} | 💪 {fmt_num(r['combat_power'])} | 🏘 {r['districts']}р."

    next_district_str = ""
    if bot_power and next_bot:
        next_district_str = f"\n\n⚔️ Следующий район #{next_bot.number}: 🤖 {fmt_num(bot_power)} мощи"
    elif not next_bot:
        next_district_str = "\n\n✅ Все районы захвачены!"

    text = (
        f"⚔️ <b>Атака — Фаза Банды</b>\n\n"
        f"🏙 Город: <b>{city.name}</b>\n"
        f"📍 Сектор {user.sector} | {city.total_districts} районов\n\n"
        f"🏘 Твоих районов: {my_d}/{total_d}\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n"
        f"🎯 Влияние: {fmt_num(user.influence)}"
        + extra_str + cd_str + next_district_str + rival_str
    )

    builder = InlineKeyboardBuilder()
    if cd > 0:
        builder.row(
            InlineKeyboardButton(text=f"⏳ КД: {fmt_ttl(cd)}", callback_data="attack_cd"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="attack"),
        )
    else:
        atk_label = (
            f"⚡ Атаковать (ещё {user.extra_attack_count + 1} атаки)"
            if user.extra_attack_count > 0 else "⚔️ Атаковать район"
        )
        builder.row(InlineKeyboardButton(text=atk_label, callback_data="do_attack"))

    if rivals:
        builder.row(InlineKeyboardButton(
            text=f"🥊 PvP ({len(rivals)} соперника)", callback_data="pvp_attack"
        ))
    builder.row(InlineKeyboardButton(text=truce_button_label(user), callback_data="truce_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return text, builder.as_markup()


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("city_page:"))
async def cb_city_page(cb: CallbackQuery, session: AsyncSession, user: User):
    page = int(cb.data.split(":")[1])
    text, kb = await build_gang_menu(session, user, page=page)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("choose_sector:"))
async def cb_choose_sector(cb: CallbackQuery, session: AsyncSession, user: User):
    sector = cb.data.split(":")[1]
    result = await game_service.choose_sector(session, user, sector)
    if result["ok"]:
        await cb.answer(f"✅ Сектор {sector} выбран!")
        # Обновляем объект user из БД чтобы sector был актуален
        await session.refresh(user)
        from app.handlers.attack import build_attack_menu
        text, kb = await build_attack_menu(session, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
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
        text, kb = await build_attack_menu(session, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "do_attack")
async def cb_do_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    lock_key = cooldown_service.attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.gang_attack_bot(session, user)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"), parse_mode="HTML"
        )
        return

    if result.get("destroyed"):
        await cb.message.edit_text(
            f"💀 <b>{result['message']}</b>",
            reply_markup=back_kb("main_menu"), parse_mode="HTML"
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    extra_left = result.get("extra_attacks_left", 0)
    extra_str = f"\n⚡ Ещё атак без КД: {extra_left}" if extra_left > 0 else ""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Атаковать снова", callback_data="attack"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await quest_service.add_progress(session, user, "attacks")
    if result["win"]:
        await quest_service.add_progress(session, user, "wins")
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
    await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "pvp_attack")
async def cb_pvp_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.gang_city_id:
        await cb.answer("Выберите город", show_alert=True)
        return
    situation = await game_service.gang_get_situation(session, user)
    rivals = situation.get("rivals", [])
    if not rivals:
        await cb.answer("Нет соперников в городе", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for r in rivals[:5]:
        builder.button(
            text=f"⚔️ {r['name']} | 💪 {fmt_num(r['combat_power'])} | 🏘 {r['districts']}р.",
            callback_data=f"gang_pvp:{r['id']}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))
    await cb.message.edit_text(
        f"🥊 <b>PvP — Выбери соперника</b>\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n\n"
        f"Победишь — заберёшь его район!",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("gang_pvp:"))
async def cb_gang_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    import html
    defender_id = int(cb.data.split(":")[1])
    result = await game_service.gang_attack_pvp(session, user, defender_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"), parse_mode="HTML"
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

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
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")