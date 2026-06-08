from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.user import User
from app.services.game_service import game_service
from app.services.cooldown_service import cooldown_service
from app.repositories.user_repo import user_repo
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_ttl
from app.utils.truce import truce_button_label
import html

router = Router()


async def build_fist_menu(session, user):
    cd_key = cooldown_service.attack_key(user.id)
    cd = await cooldown_service.get_ttl(cd_key)
    bots = await game_service.get_fist_bots(session, user)
    now = datetime.now(timezone.utc)

    extra_str = f"\n⚡ Доп. атак: {user.extra_attack_count}" if user.extra_attack_count > 0 else ""
    cd_str = f"\n⏳ КД: {fmt_ttl(cd)}" if cd > 0 else ""

    text = (
        f"✊ <b>Атака — Фаза Кулака</b>\n\n"
        f"Побед: {user.fist_wins}/10\n"
        f"Городов: {user.fist_cities_count}\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}"
        + extra_str + cd_str +
        f"\n\n<b>Выбери противника:</b>"
    )

    builder = InlineKeyboardBuilder()
    for bot in bots:
        on_cd = bot.cooldown_until and bot.cooldown_until > now
        cd_str_bot = ""
        if on_cd:
            remaining = int((bot.cooldown_until - now).total_seconds())
            cd_str_bot = f" ⏳{fmt_ttl(remaining)}"
        ratio_pct = int(bot.power_ratio * 100)
        icon = "🔒" if on_cd else "⚔️"
        builder.button(
            text=f"{icon} {bot.name} | 💪 {fmt_num(bot.current_power)} ({ratio_pct}%){cd_str_bot}",
            callback_data=f"fist_bot:{bot.id}"
        )
    builder.adjust(1)

    fist_rivals = await user_repo.get_fist_players(session, user.id)
    if fist_rivals:
        builder.button(
            text=f"🥊 PvP Кулаки ({len(fist_rivals)})",
            callback_data="fist_pvp_list"
        )
    builder.row(InlineKeyboardButton(text=truce_button_label(user), callback_data="truce_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return text, builder.as_markup()


@router.callback_query(F.data.startswith("fist_bot:"))
async def cb_fist_bot(cb: CallbackQuery, session: AsyncSession, user: User):
    bot_id = int(cb.data.split(":")[1])

    lock_key = cooldown_service.attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.fist_attack_bot(session, user, bot_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {html.escape(result['message'])}",
            reply_markup=back_kb("main_menu"), parse_mode="HTML"
        )
        return

    if result.get("destroyed"):
        await cb.message.edit_text(
            f"💀 <b>{html.escape(result['message'])}</b>",
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
        from app.utils.region_activity import record
        await record(session, user.id, "attack_fist")

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result.get("demoted"):
        king_count = result.get("king_cities_count", 0)
        need_more = max(0, 10 - king_count)
        text = (
            f"❌ <b>Поражение от {result['bot_name']}!</b>\n\n"
            f"Потеряно городов: {result['cities_lost']}\n\n"
            f"⚠️ <b>Вы понижены до фазы Короля!</b>\n"
            f"{'─' * 20}\n"
            f"🏙 Городов (Король): <b>{king_count}/10</b>\n"
            f"Ещё нужно захватить: <b>{need_more}</b>"
        )
        await cb.message.edit_text(text, reply_markup=back_kb("main_menu"), parse_mode="HTML")
        return
    if result["win"]:
        cities_gained = result.get("cities_gained", 1)
        city_sizes = result.get("city_sizes", [])
        sizes_str = ", ".join(str(s) for s in city_sizes)
        text = (
            f"✅ <b>Победа над {result['bot_name']}!{crit_str}</b>\n\n"
            f"🏙 Получено городов: <b>{cities_gained}</b> ({sizes_str} районов)\n"
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
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")


@router.callback_query(F.data == "fist_pvp_list")
async def cb_fist_pvp_list(cb: CallbackQuery, session: AsyncSession, user: User):
    rivals = await user_repo.get_fist_players(session, user.id)
    if not rivals:
        await cb.answer("Нет доступных кулаков для PvP", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for rival in rivals[:8]:
        builder.button(
            text=f"⚔️ {rival.full_name} | 💪 {fmt_num(rival.combat_power)} | 🏙 {rival.fist_cities_count}",
            callback_data=f"fist_pvp:{rival.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))
    await cb.message.edit_text(
        f"🥊 <b>PvP Кулаков</b>\n\n"
        f"💪 Твоя мощь: {fmt_num(user.combat_power)}\n\n"
        f"Выбери соперника:",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fist_pvp:"))
async def cb_fist_pvp(cb: CallbackQuery, session: AsyncSession, user: User):
    defender_id = int(cb.data.split(":")[1])

    lock_key = cooldown_service.attack_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        result = await game_service.fist_pvp_attack(session, user, defender_id)
        await session.commit()
    finally:
        await cooldown_service.release_lock(lock_key)

    if result.get("promoted"):
        await cb.message.edit_text(
            f"🎉 {result['message']}",
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
        from app.utils.region_activity import record
        await record(session, user.id, "attack_fist")

    crit_str = " ⚡КРИТ!" if result.get("is_crit") else ""
    if result.get("demoted"):
        king_count = result.get("king_cities_count", 0)
        need_more = max(0, 10 - king_count)
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n\n"
            f"⚠️ <b>Вы понижены до фазы Короля!</b>\n"
            f"{'─' * 20}\n"
            f"🏙 Городов (Король): <b>{king_count}/10</b>\n"
            f"Ещё нужно захватить: <b>{need_more}</b>"
        )
        await cb.message.edit_text(text, reply_markup=back_kb("main_menu"), parse_mode="HTML")
        return
    if result["win"]:
        text = (
            f"✅ <b>Победа в PvP!{crit_str}</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    else:
        text = (
            f"❌ <b>Поражение в PvP!</b>\n\n"
            f"Противник: {html.escape(result['defender_name'])}\n"
            f"💪 Твоя мощь: {fmt_num(result['attacker_power'])}\n"
            f"⚔️ Его мощь: {fmt_num(result['defender_power'])}"
        )
    await cb.message.edit_text(text, reply_markup=back_kb("attack"), parse_mode="HTML")