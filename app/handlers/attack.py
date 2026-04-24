from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.game_service import game_service
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.utils.keyboards.common import back_kb, confirm_kb
from app.utils.formatters import fmt_power, fmt_num, fmt_ttl, phase_label
from sqlalchemy import select, func
from app.models.city import District

router = Router()


class AttackFSM(StatesGroup):
    waiting_pvp_choice = State()


async def build_attack_menu(
    session: AsyncSession, user: User
) -> tuple[str, object]:
    from datetime import datetime, timezone

    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    # ── БАНДА ───────────────────────────────────────────────────────────────
    if user.phase == "gang":
        if not user.sector:
            builder = InlineKeyboardBuilder()
            for s in ["Н", "Х", "Ч", "Б", "М", "Ж"]:
                builder.button(
                    text=f"🌐 Сектор {s}",
                    callback_data=f"choose_sector:{s}"
                )
            builder.adjust(3)
            builder.row(InlineKeyboardButton(
                text="◀️ Назад", callback_data="main_menu"
            ))
            return (
                "⚔️ <b>Атака — Выбор сектора</b>\n\n"
                "Выбери сектор — это решение нельзя изменить!\n"
                "В каждом секторе 50 городов (5 типов × 10 штук).",
                builder.as_markup()
            )

        if not user.gang_city_id:
            cities = await city_repo.get_available_gang_cities(
                session, user.sector
            )
            builder = InlineKeyboardBuilder()
            # Группируем по типу
            type_names = {
                1: "4 района", 2: "8 районов",
                3: "16 районов", 4: "32 района", 5: "64 района"
            }
            current_type = None
            for city in cities[:30]:  # показываем первые 30
                if city.type_id != current_type:
                    current_type = city.type_id
                builder.button(
                    text=f"🏙 {city.name} [{type_names.get(city.type_id, '?')}]",
                    callback_data=f"choose_city:{city.id}"
                )
            builder.adjust(1)
            builder.row(InlineKeyboardButton(
                text="◀️ Назад", callback_data="main_menu"
            ))
            return (
                f"⚔️ <b>Выбор города — Сектор {user.sector}</b>\n\n"
                f"Выбери город. После выбора нельзя сменить\n"
                f"пока не завоюешь все районы!",
                builder.as_markup()
            )

        # Город выбран — показываем ситуацию
        situation = await game_service.gang_get_situation(session, user)
        if not situation["ok"]:
            return situation["reason"], back_kb("main_menu")

        city = situation["city"]
        my_d = situation["my_districts"]
        total_d = situation["total_districts"]
        bot_power = situation["bot_district_power"]
        rivals = situation["rivals"]
        next_bot = situation["next_bot_district"]

        # Строим текст
        extra_str = ""
        if user.extra_attack_count > 0:
            extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}"

        rival_str = ""
        if rivals:
            rival_str = "\n\n👥 <b>Соперники в городе:</b>"
            for r in rivals:
                rival_str += (
                    f"\n  ⚔️ {r['name']} | "
                    f"💪 {fmt_num(r['combat_power'])} | "
                    f"🏘 {r['districts']} р."
                )

        text = (
            f"⚔️ <b>{city.name}</b> [{city.type_id * 4} → {city.total_districts} р.]\n"
            f"📍 Сектор {user.sector}\n\n"
            f"🏘 Твоих районов: {my_d}/{total_d}\n"
            f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n"
            f"🎯 Влияние: {fmt_num(user.influence)}"
            + extra_str
            + (f"\n\n🤖 Мощь следующего района #{next_bot.number if next_bot else '?'}: {fmt_num(bot_power)}" if bot_power else "")
            + rival_str
        )

        builder = InlineKeyboardBuilder()
        if cd > 0:
            builder.row(InlineKeyboardButton(
                text=f"⏳ КД: {fmt_ttl(cd)}",
                callback_data="attack_cd"
            ))
        else:
            atk_label = "⚔️ Атаковать район"
            if user.extra_attack_count > 0:
                atk_label = f"⚡ Атаковать ({user.extra_attack_count + 1} атаки!)"
            builder.row(InlineKeyboardButton(
                text=atk_label,
                callback_data="do_attack"
            ))

        if rivals:
            builder.row(InlineKeyboardButton(
                text=f"🥊 PvP ({len(rivals)} соперника)",
                callback_data="pvp_attack"
            ))

        builder.row(InlineKeyboardButton(
            text="◀️ Главное меню", callback_data="main_menu"
        ))
        return text, builder.as_markup()

    # ── КОРОЛЬ ──────────────────────────────────────────────────────────────
    elif user.phase == "king":
        cities = await city_repo.get_available_king_cities(session, user.sector or "Н")

        from sqlalchemy import select as sa_select, func
        from app.models.city import District

        my_city_ids_r = await session.execute(
            sa_select(District.city_id).where(
                District.owner_id == user.id,
                District.is_captured == True,
            ).distinct()
        )
        my_city_ids = set(my_city_ids_r.scalars().all())

        builder = InlineKeyboardBuilder()
        # Показываем по 3 города каждого типа (5 типов × 3 = 15 кнопок)
        type_counts: dict[int, int] = {}
        for city in cities:
            type_id = city.type_id or 1
            if type_counts.get(type_id, 0) >= 3:
                continue
            type_counts[type_id] = type_counts.get(type_id, 0) + 1

            my_in_city = await session.scalar(
                sa_select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0

            if city.owner_id and city.owner_id != user.id:
                defender = await user_repo.get_by_id(session, city.owner_id)
                def_power = int(defender.combat_power * 0.7) if defender else 0
                def_str = f"👤{fmt_num(def_power)}"
            else:
                from app.data.cities import KING_DISTRICT_BASE_POWER
                bot_power = int(
                    KING_DISTRICT_BASE_POWER
                    * city.total_districts
                    * city.district_power_multiplier
                )
                def_str = f"🤖{fmt_num(bot_power)}"

            my_str = f"[моих:{my_in_city}] " if my_in_city > 0 else ""
            size_emoji = {1: "🏘", 2: "🏙", 3: "🌆", 4: "🌇", 5: "🌃"}.get(type_id, "🏙")
            builder.button(
                text=f"{size_emoji} {city.name} {my_str}{city.captured_districts}/{city.total_districts}р | {def_str}",
                callback_data=f"king_attack:{city.id}"
            )

        builder.adjust(1)
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

    # ── КУЛАК ───────────────────────────────────────────────────────────────
    elif user.phase == "fist":
        bots = await game_service.get_fist_bots(session, user)
        now = datetime.now(timezone.utc)

        extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
        text = (
            f"✊ <b>Атака — Фаза Кулака</b>\n\n"
            f"Побед: {user.fist_wins}/10\n"
            f"Городов: {user.fist_cities_count}\n"
            f"💪 Твоя мощь: {fmt_num(user.combat_power)}"
            + extra_str +
            f"\n\n<b>Выбери противника:</b>"
        )

        builder = InlineKeyboardBuilder()
        for bot in bots:
            on_cd = bot.cooldown_until and bot.cooldown_until > now
            cd_str = ""
            if on_cd:
                remaining = int((bot.cooldown_until - now).total_seconds())
                cd_str = f" ⏳{fmt_ttl(remaining)}"
            ratio_pct = int(bot.power_ratio * 100)
            icon = "🔒" if on_cd else "⚔️"
            builder.button(
                text=(
                    f"{icon} {bot.name} | "
                    f"💪 {fmt_num(bot.current_power)} ({ratio_pct}%)"
                    f"{cd_str}"
                ),
                callback_data=f"fist_bot:{bot.id}"
            )
        builder.adjust(1)

        fist_rivals = await user_repo.get_fist_players(session, user.id)
        if fist_rivals:
            builder.button(
                text=f"🥊 PvP Кулаки ({len(fist_rivals)})",
                callback_data="fist_pvp_list"
            )
        builder.row(InlineKeyboardButton(
            text="◀️ Главное меню", callback_data="main_menu"
        ))
        return text, builder.as_markup()

    # ── ИМПЕРАТОР ───────────────────────────────────────────────────────────
    elif user.phase == "emperor":
        builder = InlineKeyboardBuilder()
        if user.prestige_level < 10:
            builder.row(InlineKeyboardButton(
                text="🌟 Пробудиться",
                callback_data="do_prestige"
            ))
        builder.row(InlineKeyboardButton(
            text="◀️ Главное меню", callback_data="main_menu"
        ))
        return (
            f"🏛 <b>Фаза Императора</b>\n\n"
            f"🌟 Пробуждений: {user.prestige_level}/10\n\n"
            f"Каждое пробуждение даёт:\n"
            f"  +5% мощь | +5% бизнес | +1% тикет\n\n"
            f"❗ После пробуждения прогресс сбрасывается",
            builder.as_markup()
        )

    return "⚔️ Атака недоступна", back_kb("main_menu")


@router.callback_query(F.data == "attack")
async def cb_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    text, kb = await build_attack_menu(session, user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "attack_cd")
async def cb_attack_cd(cb: CallbackQuery, session: AsyncSession, user: User):
    cd = await cooldown_service.get_ttl(cooldown_service.attack_key(user.id))
    await cb.answer(f"⏳ Атака через {fmt_ttl(cd)}")


@router.callback_query(F.data.startswith("choose_sector:"))
async def cb_choose_sector(cb: CallbackQuery, session: AsyncSession, user: User):
    sector = cb.data.split(":")[1]
    result = await game_service.choose_sector(session, user, sector)
    if result["ok"]:
        await cb.answer(f"✅ Сектор {sector} выбран!")
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
        text, kb = await build_attack_menu(session, user)
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "do_attack")
async def cb_do_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await game_service.gang_attack_bot(session, user)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if result.get("destroyed"):
        await cb.message.edit_text(
            f"💀 <b>{result['message']}</b>",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    extra_left = result.get("extra_attacks_left", 0)
    extra_str = f"\n⚡ Ещё атак без КД: {extra_left}" if extra_left > 0 else ""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⚔️ Атаковать снова", callback_data="attack"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    if result["win"]:
        crit_str = " ⚡<b>КРИТ!</b>" if result.get("is_crit") else ""
        text = (
            f"✅ <b>Победа!{crit_str}</b>\n\n"
            f"Район #{result['district_num']} захвачен!\n"
            f"Твоих районов: {result['my_districts']}/{result['total']}\n"
            f"Районов в городе: {result['city_captured']}/{result['total']}\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🏴 Мощь района: {fmt_num(result['district_power'])}"
            + extra_str
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"Район потерян!\n"
            f"Твоих районов: {result['my_districts']}\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🏴 Мощь района: {fmt_num(result['district_power'])}"
            + extra_str
        )

    await cb.message.edit_text(
        text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )


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
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="attack"
    ))
    await cb.message.edit_text(
        f"🥊 <b>PvP — Выбери соперника</b>\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n\n"
        f"Победишь — заберёшь его район!",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("gang_pvp:"))
async def cb_gang_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    defender_id = int(cb.data.split(":")[1])
    result = await game_service.gang_attack_pvp(session, user, defender_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}\n\n"
            f"+1 район получен!"
        )
    else:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    await cb.message.edit_text(
        text, reply_markup=back_kb("attack"), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("king_attack:"))
async def cb_king_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])
    result = await game_service.king_attack(session, user, city_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа!{crit_str}</b>\n\n"
            f"Город: <b>{result['city']}</b>\n"
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
            f"Город: <b>{result['city']}</b>\n"
            f"Районов в городе: {result.get('city_captured', 0)}/{result.get('city_total', 0)}\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🤖 Мощь противника: {fmt_num(result['bot_power'])}"
        )
    await cb.message.edit_text(
        text, reply_markup=back_kb("attack"), parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("fist_bot:"))
async def cb_fist_bot(cb: CallbackQuery, session: AsyncSession, user: User):
    bot_id = int(cb.data.split(":")[1])
    result = await game_service.fist_attack_bot(session, user, bot_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if result.get("destroyed"):
        await cb.message.edit_text(
            f"💀 <b>{result['message']}</b>",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа над {result['bot_name']}!{crit_str}</b>\n\n"
            f"Получено городов: +{result['cities_gained']}\n"
            f"Всего городов: {result['fist_cities']}\n"
            f"Побед над кулаками: {result['fist_wins']}/10\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🤖 Мощь {result['bot_name']}: {fmt_num(result['bot_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение от {result['bot_name']}!</b>\n\n"
            f"Потеряно городов: {result['cities_lost']}\n"
            f"Осталось городов: {result['fist_cities']}\n\n"
            f"💪 Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"🤖 Мощь {result['bot_name']}: {fmt_num(result['bot_power'])}"
        )
    await cb.message.edit_text(
        text, reply_markup=back_kb("attack"), parse_mode="HTML"
    )


@router.callback_query(F.data == "fist_pvp_list")
async def cb_fist_pvp_list(cb: CallbackQuery, session: AsyncSession, user: User):
    rivals = await user_repo.get_fist_players(session, user.id)
    if not rivals:
        await cb.answer("Нет доступных кулаков для PvP", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for rival in rivals[:8]:
        builder.button(
            text=(
                f"⚔️ {rival.full_name} | "
                f"💪 {fmt_num(rival.combat_power)} | "
                f"🏙 {rival.fist_cities_count}"
            ),
            callback_data=f"fist_pvp:{rival.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="attack"
    ))
    await cb.message.edit_text(
        f"🥊 <b>PvP Кулаков</b>\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n\n"
        f"Выбери соперника:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fist_pvp:"))
async def cb_fist_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    defender_id = int(cb.data.split(":")[1])
    result = await game_service.fist_pvp_attack(session, user, defender_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    await cb.message.edit_text(
        text, reply_markup=back_kb("attack"), parse_mode="HTML"
    )


@router.callback_query(F.data == "do_prestige")
async def cb_do_prestige(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.prestige_service import prestige_service
    ok, reason = prestige_service.can_prestige(user)
    if not ok:
        await cb.answer(reason, show_alert=True)
        return
    await cb.message.edit_text(
        f"🌟 <b>Пробуждение</b>\n\n"
        f"Уровень: {user.prestige_level}/10\n\n"
        f"После пробуждения:\n"
        f"✅ +5% к боевой мощи навсегда\n"
        f"✅ +5% к доходу навсегда\n"
        f"✅ +1% к шансу тикета навсегда\n\n"
        f"❌ Весь прогресс будет сброшен!\n"
        f"(донаты и пробуждения сохраняются)\n\n"
        f"Подтвердить?",
        reply_markup=confirm_kb("prestige_confirm", "attack"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "prestige_confirm")
async def cb_prestige_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.prestige_service import prestige_service
    result = await prestige_service.do_prestige(session, user)
    if result["ok"]:
        await cb.message.edit_text(
            f"🌟 <b>Пробуждение {result['level']}/10!</b>\n\n"
            f"Прогресс сброшен. Начинай снова!",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
    else:
        await cb.answer(result["reason"], show_alert=True)