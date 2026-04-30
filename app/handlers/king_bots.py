from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.user import User
from app.services.king_bot_service import king_bot_service
from app.services.cooldown_service import cooldown_service
from app.utils.formatters import fmt_num

router = Router()


@router.callback_query(F.data == "king_bots_menu")
async def cb_king_bots_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "king":
        await cb.answer("Доступно только на этапе Короля!", show_alert=True)
        return

    bots = await king_bot_service.get_or_create_bots(session, user)

    # Проверяем КД атаки
    cd_key = f"king_bot_attack:{user.id}"
    attack_on_cd = await cooldown_service.is_on_cooldown(cd_key)
    attack_ttl = await cooldown_service.get_ttl(cd_key) if attack_on_cd else 0

    builder = InlineKeyboardBuilder()
    for bot in bots:
        status = king_bot_service.format_bot_status(bot)
        now = datetime.now(timezone.utc)
        on_cd = bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now
        icon = "⏳" if on_cd else "⚔️"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {bot.name} | {status}",
            callback_data=f"king_bot_info:{bot.id}"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))

    cd_str = f"\n⏳ КД атаки: {cooldown_service.format_ttl(attack_ttl)}" if attack_on_cd else ""

    await cb.message.edit_text(
        f"🤖 <b>Боты-короли</b>\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}"
        f"{cd_str}\n\n"
        f"Побеждай ботов чтобы получить NHCoin!\n"
        f"После победы бот уходит в КД на 1 час и становится сильнее.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("king_bot_info:"))
async def cb_king_bot_info(cb: CallbackQuery, session: AsyncSession, user: User):
    bot_id = int(cb.data.split(":")[1])
    from app.models.king_bot import KingBot
    from sqlalchemy import select
    result = await session.execute(
        select(KingBot).where(KingBot.id == bot_id, KingBot.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    if not bot:
        await cb.answer("Бот не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    on_cd = bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now

    cd_key = f"king_bot_attack:{user.id}"
    attack_on_cd = await cooldown_service.is_on_cooldown(cd_key)
    attack_ttl = await cooldown_service.get_ttl(cd_key) if attack_on_cd else 0

    builder = InlineKeyboardBuilder()

    if on_cd:
        remaining = int((bot.cooldown_until - now).total_seconds())
        builder.row(InlineKeyboardButton(
            text=f"⏳ КД: {cooldown_service.format_ttl(remaining)}",
            callback_data="noop_king_bot"
        ))
    elif attack_on_cd:
        builder.row(InlineKeyboardButton(
            text=f"⏳ Атака: {cooldown_service.format_ttl(attack_ttl)}",
            callback_data="noop_king_bot"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="⚔️ Атаковать",
            callback_data=f"king_bot_attack:{bot_id}"
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

    status_str = ""
    if on_cd:
        remaining = int((bot.cooldown_until - now).total_seconds())
        status_str = f"⏳ Восстанавливается: {cooldown_service.format_ttl(remaining)}"
    else:
        can_win = "✅" if user.combat_power >= bot.power else "❌"
        status_str = f"{can_win} Твоя мощь {'≥' if user.combat_power >= bot.power else '<'} мощи бота"

    await cb.message.edit_text(
        f"🤖 <b>{bot.name}</b>\n\n"
        f"💪 Мощь бота: {fmt_num(bot.power)}\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n\n"
        f"🏘 Захвачено: {bot.districts_captured}/{bot.districts_total}\n"
        f"{progress_bar} {pct}%\n\n"
        f"{status_str}\n\n"
        f"💰 Награда за победу: {fmt_num(bot.power // 10)} NHCoin",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("king_bot_attack:"))
async def cb_king_bot_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    bot_id = int(cb.data.split(":")[1])
    result = await king_bot_service.attack_bot(session, user, bot_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    if result["win"]:
        if result["fully_captured"]:
            await cb.answer(
                f"🏆 {result['bot_name']} повержен!\n"
                f"+{fmt_num(result['coins_reward'])} NHCoin",
                show_alert=True
            )
            await cb.message.edit_text(
                f"🏆 <b>Победа!</b>\n\n"
                f"Ты полностью захватил {result['bot_name']}!\n\n"
                f"💥 Твоя мощь: {fmt_num(result['user_power'])}\n"
                f"🤖 Мощь бота: {fmt_num(result['bot_power'])}\n\n"
                f"💰 Получено: +{fmt_num(result['coins_reward'])} NHCoin\n"
                f"⏳ Бот уйдёт в КД на 1 час и станет сильнее!",
                reply_markup=__import__("aiogram.utils.keyboard", fromlist=["InlineKeyboardBuilder"]).InlineKeyboardBuilder().row(
                    InlineKeyboardButton(text="◀️ К ботам", callback_data="king_bots_menu")
                ).as_markup(),
                parse_mode="HTML",
            )
        else:
            await cb.answer(
                f"✅ +{result['gained']} районов!\n"
                f"{result['captured']}/{result['total']}",
                show_alert=True
            )
            await cb_king_bot_info(cb, session, user)
    else:
        await cb.answer(
            f"❌ Поражение!\n"
            f"Мощь бота: {fmt_num(result['bot_power'])}",
            show_alert=True
        )
        await cb_king_bot_info(cb, session, user)


@router.callback_query(F.data == "noop_king_bot")
async def cb_noop_king_bot(cb: CallbackQuery):
    await cb.answer()