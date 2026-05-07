from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from app.services.quest_service import quest_service
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.models.king_bot import KingBot
from app.services.king_bot_service import king_bot_service
from app.services.cooldown_service import cooldown_service
from app.utils.formatters import fmt_num

router = Router()


async def _get_king_cities_count(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func
    from app.models.city import District
    return await session.scalar(
        select(func.count(func.distinct(District.city_id))).where(
            District.owner_id == user_id,
            District.is_captured == True,
        )
    ) or 0


@router.callback_query(F.data == "king_bots_menu")
async def cb_king_bots_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "king":
        await cb.answer("Доступно только на этапе Короля!", show_alert=True)
        return

    cities_count = await _get_king_cities_count(session, user.id)
    if cities_count >= 9:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⚔️ Атаковать города", callback_data="attack"))
        try:
            await cb.message.edit_text(
                f"🏙 <b>Уже завоёвано {cities_count}/10 городов!</b>\n\n"
                f"Последний город нужно захватить через обычную атаку городов — не через ботов.\n\n"
                f"Иди завоёвывай последний город!",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    bots = await king_bot_service.get_or_create_bots(session, user)
    now = datetime.now(timezone.utc)

    cd_key = f"king_bot_attack:{user.id}"
    attack_on_cd = await cooldown_service.is_on_cooldown(cd_key)
    attack_ttl = await cooldown_service.get_ttl(cd_key) if attack_on_cd else 0

    builder = InlineKeyboardBuilder()
    lines = []

    for bot in bots:
        on_cd = bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now
        pct = int(bot.districts_captured / bot.districts_total * 100) if bot.districts_total > 0 else 0

        if on_cd:
            remaining = int((bot.cooldown_until - now).total_seconds())
            status = f"⏳ {cooldown_service.format_ttl(remaining)}"
            icon = "🔒"
        else:
            can = "✅" if user.combat_power >= bot.power else "❌"
            status = f"{can} {bot.districts_captured}/{bot.districts_total}р"
            icon = "⚔️"

        builder.row(InlineKeyboardButton(
            text=f"{icon} {bot.name} | {fmt_num(bot.power)} | {status}",
            callback_data=f"king_bot_info:{bot.id}"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))

    cd_str = f"\n⏳ КД атаки: {cooldown_service.format_ttl(attack_ttl)}" if attack_on_cd else ""

    try:
        await cb.message.edit_text(
            f"🤖 <b>Боты-короли</b>\n\n"
            f"💪 Твоя мощь: {fmt_num(user.combat_power)}"
            f"{cd_str}\n\n"
            f"Побеждай ботов чтобы получить города NHCoin!\n"
            f"Город выдается только после полной пробеды над ботом!\n"
            f"После победы бот уходит в КД 1 час и усиливается.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("king_bot_info:"))
async def cb_king_bot_info(cb: CallbackQuery, session: AsyncSession, user: User):
    bot_id = int(cb.data.split(":")[1])
    result = await session.execute(
        select(KingBot).where(KingBot.id == bot_id, KingBot.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    if not bot:
        await cb.answer("Бот не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    on_cd = bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now

    # Сбрасываем если КД прошёл
    if bot.is_defeated and (not bot.cooldown_until or bot.cooldown_until <= now):
        bot.is_defeated = False
        bot.districts_captured = 0
        from app.database import AsyncSessionFactory
        await session.flush()
        on_cd = False

    cd_key = f"king_bot_attack:{user.id}"
    attack_on_cd = await cooldown_service.is_on_cooldown(cd_key)
    attack_ttl = await cooldown_service.get_ttl(cd_key) if attack_on_cd else 0

    builder = InlineKeyboardBuilder()

    if on_cd:
        remaining = int((bot.cooldown_until - now).total_seconds())
        builder.row(InlineKeyboardButton(
            text=f"🔒 КД бота: {cooldown_service.format_ttl(remaining)}",
            callback_data="noop_king_bot"
        ))
    elif attack_on_cd:
        builder.row(InlineKeyboardButton(
            text=f"⏳ Атака: {cooldown_service.format_ttl(attack_ttl)}",
            callback_data="noop_king_bot"
        ))
    else:
        can_win = user.combat_power >= bot.power
        if can_win:
            builder.row(InlineKeyboardButton(
                text="⚔️ Атаковать!",
                callback_data=f"king_bot_attack:{bot_id}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"❌ Слишком слабый (нужно {fmt_num(bot.power)})",
                callback_data="noop_king_bot"
            ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"king_bot_info:{bot_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="king_bots_menu"
    ))

    pct = int(bot.districts_captured / bot.districts_total * 100) if bot.districts_total > 0 else 0
    bar_filled = int(pct / 10)
    progress_bar = "🟩" * bar_filled + "⬛" * (10 - bar_filled)

    can_win = user.combat_power >= bot.power
    power_diff = user.combat_power - bot.power
    power_str = f"+{fmt_num(power_diff)}" if power_diff >= 0 else fmt_num(power_diff)

    if on_cd:
        remaining = int((bot.cooldown_until - now).total_seconds())
        status_str = f"🔒 Восстанавливается: {cooldown_service.format_ttl(remaining)}"
    else:
        status_str = f"{'✅ Можешь победить' if can_win else '❌ Слишком слабый'} ({power_str})"

    reward = bot.power // 10
    next_power = int(bot.power * 1.5)

    try:
        await cb.message.edit_text(
            f"🤖 <b>{bot.name}</b>\n"
            f"📊 Слот {bot.slot}/5\n\n"
            f"{'─' * 20}\n"
            f"💪 Мощь бота: <b>{fmt_num(bot.power)}</b>\n"
            f"💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>\n"
            f"📈 Разница: {power_str}\n\n"
            f"{'─' * 20}\n"
            f"🏘 Прогресс захвата:\n"
            f"{progress_bar} {pct}%\n"
            f"{bot.districts_captured}/{bot.districts_total} районов\n\n"
            f"{'─' * 20}\n"
            f"{status_str}\n\n"
            f"💰 Награда за победу: <b>{fmt_num(reward)} NHCoin</b>\n"
            f"📈 После победы мощь: <b>{fmt_num(next_power)}</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("king_bot_attack:"))
async def cb_king_bot_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    cities_count = await _get_king_cities_count(session, user.id)
    if cities_count >= 9:
        await cb.answer(
            f"У тебя уже {cities_count}/10 городов! Последний захвати через обычную атаку городов.",
            show_alert=True,
        )
        return

    bot_id = int(cb.data.split(":")[1])
    result = await king_bot_service.attack_bot(session, user, bot_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await quest_service.add_progress(session, user, "attacks")
    if result["win"]:
        await quest_service.add_progress(session, user, "wins")
        if result["fully_captured"]:
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(
                text="🤖 К ботам", callback_data="king_bots_menu"
            ))
            builder.row(InlineKeyboardButton(
                text="⚔️ В атаку", callback_data="attack"
            ))
            try:
                await cb.message.edit_text(
                    f"🏆 <b>Победа!</b>\n\n"
                    f"Ты полностью захватил <b>{result['bot_name']}</b>!\n\n"
                    f"{'─' * 20}\n"
                    f"💥 Твоя мощь: {fmt_num(result['user_power'])}\n"
                    f"🤖 Мощь бота: {fmt_num(result['bot_power'])}\n\n"
                    f"💰 Получено: <b>+{fmt_num(result['coins_reward'])} NHCoin</b>\n"
                    f"⚡ +500 влияния\n"
                    f"🏙 Городов с районами: <b>{result['cities_count']}/10</b>\n\n"
                    f"{'─' * 20}\n"
                    f"⏳ Бот уходит в КД на 1 час\n"
                    f"📈 Новая мощь бота: {fmt_num(int(result['bot_power']))}",
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        else:
            await cb.answer(
                f"✅ +{result['gained']} районов!\n"
                f"{result['captured']}/{result['total']} захвачено"
                + (f"\n⚡ Доп. атак: {result['extra_attacks_left']}" if result.get('extra_attacks_left', 0) > 0 else ""),
                show_alert=True
            )
            await cb_king_bot_info(cb, session, user)
    else:
        await cb.answer(
            f"❌ Поражение!\n"
            f"Твоя мощь: {fmt_num(result['user_power'])}\n"
            f"Мощь бота: {fmt_num(result['bot_power'])}",
            show_alert=True
        )
        await cb_king_bot_info(cb, session, user)


@router.callback_query(F.data == "noop_king_bot")
async def cb_noop_king_bot(cb: CallbackQuery):
    await cb.answer()