from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.game_service import game_service
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.utils.keyboards import (
    back_kb, sector_kb, cities_kb, attack_action_kb
)
from app.utils.formatters import fmt_power, fmt_num, phase_label

router = Router()


class AttackFSM(StatesGroup):
    waiting_pvp_choice = State()


async def build_attack_menu(session: AsyncSession, user: User) -> tuple[str, object]:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from app.utils.formatters import fmt_ttl

    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)

    if user.phase == "gang":
        if not user.sector:
            text = (
                "⚔️ <b>Атака — Выбор сектора</b>\n\n"
                "Выберите сектор — это решение нельзя изменить!\n"
                "Каждый сектор содержит 50 городов."
            )
            builder = InlineKeyboardBuilder()
            sectors = ["Н", "Х", "Ч", "Б", "М", "Ж"]
            for s in sectors:
                builder.button(text=f"🌐 Сектор {s}", callback_data=f"choose_sector:{s}")
            builder.adjust(3)
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
            kb = builder.as_markup()

        elif not user.gang_city_id:
            cities = await city_repo.get_available_gang_cities(session, user.sector)
            text = (
                f"⚔️ <b>Атака — Выбор города</b>\n\n"
                f"Сектор: {user.sector}\n"
                f"Выберите город для захвата:"
            )
            builder = InlineKeyboardBuilder()
            for city in cities:
                status = f"{city.captured_districts}/{city.total_districts}"
                builder.button(
                    text=f"{city.name} [{status}]",
                    callback_data=f"choose_city:{city.id}"
                )
            builder.adjust(1)
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
            kb = builder.as_markup()

        else:
            city = await city_repo.get_city(session, user.gang_city_id)
            from sqlalchemy import select, func
            from app.models.city import District
            r = await session.execute(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == user.gang_city_id,
                )
            )
            districts_owned = r.scalar() or 0

            rivals = await user_repo.get_players_in_city(
                session, user.gang_city_id, user.id
            )

            text = (
                f"⚔️ <b>Атака — {city.name if city else 'Город'}</b>\n\n"
                f"📍 Сектор: {user.sector}\n"
                f"🏙 Районов: {districts_owned}/{city.total_districts if city else '?'}\n"
                f"⚔️ Мощь: {fmt_power(user.combat_power)}\n"
                f"🎯 Влияние: {fmt_num(user.influence)}"
                + (f"\n👥 Соперников: {len(rivals)}" if rivals else "")
            )

            builder = InlineKeyboardBuilder()
            if cd > 0:
                builder.row(InlineKeyboardButton(
                    text=f"⏳ КД: {fmt_ttl(cd)}",
                    callback_data="attack_cd"
                ))
            else:
                builder.row(InlineKeyboardButton(
                    text="⚔️ Атаковать район",
                    callback_data="do_attack"
                ))
                if user.extra_attack_count > 0:
                    builder.row(InlineKeyboardButton(
                        text=f"⚡ Доп. атака ({user.extra_attack_count})",
                        callback_data="do_attack"
                    ))
            if rivals:
                builder.row(InlineKeyboardButton(
                    text="🥊 PvP атака",
                    callback_data="pvp_attack"
                ))
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
            kb = builder.as_markup()

    elif user.phase == "king":
        cities = await city_repo.get_available_king_cities(session, user.sector or "Н")
        text = (
            f"⚔️ <b>Атака — Фаза Короля</b>\n\n"
            f"Городов захвачено: {user.king_cities_count}/10\n"
            f"⚔️ Мощь: {fmt_power(user.combat_power)}\n\n"
            f"Выберите город для атаки:"
        )
        builder = InlineKeyboardBuilder()
        for city in cities:
            status = "✅" if city.is_fully_captured else f"{city.captured_districts}/{city.total_districts}"
            builder.button(
                text=f"{city.name} [{status}]",
                callback_data=f"king_attack:{city.id}"
            )
        builder.adjust(1)
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        kb = builder.as_markup()

    elif user.phase == "fist":
        bots = await game_service.get_fist_bots(session, user)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        text = (
            f"⚔️ <b>Атака — Фаза Кулака</b>\n\n"
            f"Побед: {user.fist_wins}/10\n"
            f"Городов: {user.fist_cities_count}\n"
            f"⚔️ Мощь: {fmt_power(user.combat_power)}\n\n"
            f"<b>Выбери бота:</b>"
        )
        builder = InlineKeyboardBuilder()
        for bot in bots:
            on_cd = bot.cooldown_until and bot.cooldown_until > now
            cd_str = ""
            if on_cd:
                remaining = int((bot.cooldown_until - now).total_seconds())
                cd_str = f" ⏳{cooldown_service.format_ttl(remaining)}"
            ratio_pct = int(bot.power_ratio * 100)
            builder.button(
                text=f"{'🔒' if on_cd else '⚔️'} {bot.name} ({ratio_pct}%){cd_str}",
                callback_data=f"fist_bot:{bot.id}"
            )
        builder.adjust(1)
        fist_rivals = await user_repo.get_fist_players(session, user.id)
        if fist_rivals:
            builder.button(
                text=f"🥊 PvP ({len(fist_rivals)})",
                callback_data="fist_pvp_list"
            )
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        kb = builder.as_markup()

    elif user.phase == "emperor":
        text = (
            f"🏛 <b>Фаза Императора</b>\n\n"
            f"🌟 Пробуждение: {user.prestige_level}/10\n\n"
            f"Каждое пробуждение:\n"
            f"+5% мощь | +5% бизнес | +1% тикет\n\n"
            f"❗ Прогресс будет сброшен"
        )
        builder = InlineKeyboardBuilder()
        if user.prestige_level < 10:
            builder.row(InlineKeyboardButton(
                text="🌟 Пробудиться", callback_data="do_prestige"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        kb = builder.as_markup()

    else:
        text = "⚔️ Атака недоступна"
        from app.utils.keyboards.common import back_kb
        kb = back_kb("main_menu")

    return text, kb


@router.callback_query(F.data == "attack")
async def cb_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    text, kb = await build_attack_menu(session, user)
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
        text, kb = await build_attack_menu(session, user)
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data.startswith("choose_city:"))
async def cb_choose_city(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])
    result = await game_service.choose_gang_city(session, user, city_id)
    if result["ok"]:
        await cb.answer(f"✅ Город {result['city']} выбран!")
        text, kb = await build_attack_menu(session, user)
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "do_attack")
async def cb_do_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await game_service.gang_attack(session, user)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 <b>{result['message']}</b>\n\n"
            f"Добро пожаловать в фазу {phase_label(result['new_phase'])}!",
            reply_markup=back_kb("attack"),
            parse_mode="HTML",
        )
        return

    if result.get("destroyed"):
        await cb.message.edit_text(
            f"💀 <b>{result['message']}</b>",
            reply_markup=back_kb("attack"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    if result["win"]:
        crit_str = " ⚡<b>КРИТ!</b>" if result.get("is_crit") else ""
        text = (
            f"✅ <b>Победа!</b>{crit_str}\n\n"
            f"Район {result['district']} захвачен!\n"
            f"Прогресс: {result['captured']}/{result['total']}\n\n"
            f"Ваша мощь: {fmt_power(result['user_power'])}\n"
            f"Мощь района: {fmt_power(result['district_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"Район потерян!\n"
            f"Осталось районов: {result['districts_left']}\n\n"
            f"Ваша мощь: {fmt_power(result['user_power'])}\n"
            f"Мощь района: {fmt_power(result['district_power'])}"
        )

    text, kb = await build_attack_menu(session, user)
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "pvp_attack")
async def cb_pvp_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    rivals = await user_repo.get_players_in_city(
        session, user.gang_city_id, user.id
    )
    if not rivals:
        await cb.answer("Нет соперников в городе", show_alert=True)
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for rival in rivals[:5]:
        builder.button(
            text=f"⚔️ {rival.full_name} | {fmt_power(rival.combat_power)}",
            callback_data=f"gang_pvp:{rival.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ К атаке", callback_data="attack"))

    await cb.message.edit_text(
        "🥊 <b>PvP — Выберите соперника</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("gang_pvp:"))
async def cb_gang_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    defender_id = int(cb.data.split(":")[1])
    result = await game_service.gang_pvp_attack(session, user, defender_id)
    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"Ваша мощь: {fmt_power(result['attacker_power'])}\n"
            f"Его мощь: {fmt_power(result['defender_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"Ваша мощь: {fmt_power(result['attacker_power'])}\n"
            f"Его мощь: {fmt_power(result['defender_power'])}"
        )
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")


@router.callback_query(F.data.startswith("king_attack:"))
async def cb_king_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    city_id = int(cb.data.split(":")[1])
    result = await game_service.king_attack(session, user, city_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 <b>{result['message']}</b>",
            reply_markup=back_kb("attack"),
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
            f"Город: {result['city']}\n"
            f"Захвачено городов: {result['cities_count']}/10\n"
            f"Ваша мощь: {fmt_power(result['user_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение!</b>\n\n"
            f"Город: {result['city']}\n"
            f"Ваша мощь: {fmt_power(result['user_power'])}\n"
            f"Мощь бота: {fmt_power(result['bot_power'])}"
        )
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")


@router.callback_query(F.data.startswith("fist_bot:"))
async def cb_fist_bot(cb: CallbackQuery, session: AsyncSession, user: User):
    bot_id = int(cb.data.split(":")[1])
    result = await game_service.fist_attack_bot(session, user, bot_id)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 <b>{result['message']}</b>",
            reply_markup=back_kb("attack"),
            parse_mode="HTML",
        )
        return

    if result.get("destroyed"):
        await cb.message.edit_text(
            f"💀 <b>{result['message']}</b>",
            reply_markup=back_kb("attack"),
            parse_mode="HTML",
        )
        return

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    if result["win"]:
        crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
        text = (
            f"✅ <b>Победа над {result['bot_name']}!{crit_str}</b>\n\n"
            f"Получено городов: +{result['cities_gained']}\n"
            f"Всего городов: {result['fist_cities']}\n"
            f"Побед над кулаками: {result['fist_wins']}/10\n\n"
            f"Ваша мощь: {fmt_power(result['user_power'])}\n"
            f"Мощь бота: {fmt_power(result['bot_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение от {result['bot_name']}!</b>\n\n"
            f"Потеряно городов: {result['cities_lost']}\n"
            f"Осталось городов: {result['fist_cities']}\n\n"
            f"Ваша мощь: {fmt_power(result['user_power'])}\n"
            f"Мощь бота: {fmt_power(result['bot_power'])}"
        )
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")


@router.callback_query(F.data == "fist_pvp_list")
async def cb_fist_pvp_list(cb: CallbackQuery, session: AsyncSession, user: User):
    rivals = await user_repo.get_fist_players(session, user.id)
    if not rivals:
        await cb.answer("Нет доступных кулаков для PvP", show_alert=True)
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for rival in rivals[:8]:
        builder.button(
            text=f"⚔️ {rival.full_name} | {fmt_power(rival.combat_power)} | {rival.fist_cities_count}🏙",
            callback_data=f"fist_pvp:{rival.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="attack"))
    await cb.message.edit_text(
        "🥊 <b>PvP Кулаков — выберите соперника</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fist_pvp:"))
async def cb_fist_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    defender_id = int(cb.data.split(":")[1])
    result = await game_service.fist_pvp_attack(session, user, defender_id)
    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result["win"]:
        text = (
            f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"Ваша мощь: {fmt_power(result['attacker_power'])}\n"
            f"Его мощь: {fmt_power(result['defender_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {result['defender_name']}\n"
            f"Ваша мощь: {fmt_power(result['attacker_power'])}\n"
            f"Его мощь: {fmt_power(result['defender_power'])}"
        )
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")


@router.callback_query(F.data == "do_prestige")
async def cb_do_prestige(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.prestige_service import prestige_service
    from app.utils.keyboards import confirm_kb
    ok, reason = prestige_service.can_prestige(user)
    if not ok:
        await cb.answer(reason, show_alert=True)
        return
    await cb.message.edit_text(
        f"🌟 <b>Пробуждение</b>\n\n"
        f"Текущий уровень: {user.prestige_level}/10\n\n"
        f"После пробуждения:\n"
        f"✅ +5% к боевой мощи\n"
        f"✅ +5% к доходу\n"
        f"✅ +1% к шансу тикета\n\n"
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
            f"🌟 <b>Пробуждение {result['level']}/10 завершено!</b>\n\n"
            f"Прогресс сброшен. Начинайте новый путь к вершине!",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
    else:
        await cb.answer(result["reason"], show_alert=True)