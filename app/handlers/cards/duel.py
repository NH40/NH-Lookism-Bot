"""UI дуэлей карточек (vs бот / vs игрок)."""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.cards.duel import duel_service
from app.services.cooldown_service import cooldown_service
from app.services.quest_service import quest_service
from app.utils.formatters import fmt_power, fmt_ttl
from app.data.characters import RANK_EMOJI
from app.constants.cards import BOT_TIERS, LEVEL_LABELS

router = Router()


class DuelFSM(StatesGroup):
    waiting_opponent = State()


# ── Меню ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "duel_menu")
async def cb_duel_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.models.skill import UserMastery
    from sqlalchemy import select as sa_select
    ttl = await cooldown_service.get_ttl(cooldown_service.duel_bot_key(user.id))
    cd_str = f"⏳ {fmt_ttl(ttl)}" if ttl > 0 else "✅ Готов"
    pvp_ttl = await cooldown_service.get_ttl(cooldown_service.duel_pvp_key(user.id))
    pvp_cd_str = f"⏳ {fmt_ttl(pvp_ttl)}" if pvp_ttl > 0 else "✅ Готов"
    dust = getattr(user, "card_dust", 0)

    # Расчёт текущего КД-бонуса
    mastery = await session.scalar(
        sa_select(UserMastery).where(UserMastery.user_id == user.id)
    )
    speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    speed_level = min(4, (mastery.speed if mastery else 0) + getattr(user, "clan_land_speed_mastery_bonus", 0))
    raw_speed = speed_levels.get(speed_level, 0)
    speed_pct = int(raw_speed * getattr(user, "skill_path_bonus_multiplier", 1.0))
    from app.constants.cards import DUEL_BOT_CD_BASE, DUEL_PVP_CD_BASE, DUEL_DONAT_CD_REDUCTION, DUEL_MIN_CD
    donat_pct = DUEL_DONAT_CD_REDUCTION if getattr(user, "donat_duel_cd", False) else 0
    flow_pct = getattr(user, "all_cd_reduction", 0) or 0
    total_cd_reduction = speed_pct + donat_pct + flow_pct
    effective_cd = max(DUEL_MIN_CD, int(DUEL_BOT_CD_BASE * (1 - total_cd_reduction / 100)))
    effective_cd_str = fmt_ttl(effective_cd)

    cd_bonus_lines = []
    if speed_pct:
        cd_bonus_lines.append(f"  ⚡ Мастерство скорости: -{speed_pct}%")
    if donat_pct:
        cd_bonus_lines.append(f"  💎 Донат ускорение: -{donat_pct}%")
    if flow_pct:
        cd_bonus_lines.append(f"  🌊 Сет Потока: -{flow_pct}%")
    cd_bonus_str = ("\n" + "\n".join(cd_bonus_lines)) if cd_bonus_lines else ""

    builder = InlineKeyboardBuilder()
    for tier_id, cfg in BOT_TIERS.items():
        cd_mark = " ⏳" if ttl > 0 else ""
        builder.row(InlineKeyboardButton(
            text=f"{cfg['emoji']} {cfg['name']}{cd_mark}",
            callback_data=f"duel_bot:{tier_id}",
        ))
    pvp_mark = " ⏳" if pvp_ttl > 0 else ""
    builder.row(InlineKeyboardButton(text=f"⚔️ Против игрока{pvp_mark}", callback_data="duel_pvp"))
    builder.row(InlineKeyboardButton(text="⚡ Авто-колода (5 сильнейших)", callback_data="duel_auto_deck"))
    builder.row(InlineKeyboardButton(text="🗑 Освободить колоду", callback_data="deck_clear_all"))
    builder.row(InlineKeyboardButton(text="◀️ К колоде", callback_data="deck"))

    text = (
        f"⚔️ <b>Дуэли</b>\n\n"
        f"💎 Пыль: {fmt_power(dust)}\n"
        f"🤖 КД бота: {cd_str}\n"
        f"👤 КД PvP: {pvp_cd_str}\n"
        f"⏱ Базовый КД: {fmt_ttl(DUEL_BOT_CD_BASE)} → {effective_cd_str}"
        f"{cd_bonus_str}\n\n"
        f"Команда = 5 из колоды + 5 случайных\n"
        f"Победитель — у кого выше суммарная мощь\n\n"
        f"Выбери противника:"
    )
    markup = builder.as_markup()
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()


# ── Авто-колода ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "duel_auto_deck")
async def cb_duel_auto_deck(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.models.character import UserCharacter
    from app.models.card_deck import UserDeck
    from sqlalchemy import select as sa_select

    # Берём 5 карточек с наибольшей мощью
    top5 = (await session.execute(
        sa_select(UserCharacter)
        .where(UserCharacter.user_id == user.id)
        .order_by(UserCharacter.power.desc())
        .limit(5)
    )).scalars().all()

    if not top5:
        await cb.answer("У тебя нет карточек!", show_alert=True)
        return

    # Очищаем колоду и выставляем новые слоты
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(UserDeck).where(UserDeck.user_id == user.id))
    await session.flush()

    for slot, uc in enumerate(top5, start=1):
        session.add(UserDeck(user_id=user.id, slot=slot, char_id=uc.id))

    await session.commit()
    await cb.answer("⚡ Колода собрана из 5 сильнейших!", show_alert=False)
    await cb_duel_menu(cb, session, user)


# ── Дуэль с ботом ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("duel_bot:"))
async def cb_duel_bot(cb: CallbackQuery, session: AsyncSession, user: User):
    tier = cb.data.split(":")[1]
    if tier not in BOT_TIERS:
        await cb.answer("Неизвестный тир", show_alert=True)
        return

    # Лок: предотвращает TOCTOU между is_on_cooldown и set_cooldown
    # (два параллельных запроса могут оба пройти проверку КД)
    lock_key = cooldown_service.duel_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Подожди...", show_alert=False)
        return

    await cb.answer()
    try:
        await cb.message.edit_text("⚔️ Дуэль начинается...")
    except Exception:
        pass

    result = await duel_service.duel_vs_bot(session, user, tier)
    if result["ok"]:
        await quest_service.add_progress(session, user, "card_duel")
        from app.utils.region_activity import record
        await record(session, user.id, "duel")
    await session.commit()

    if not result["ok"]:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ К дуэлям", callback_data="duel_menu"))
        try:
            await cb.message.edit_text(
                f"❌ {result['reason']}", reply_markup=builder.as_markup(), parse_mode="HTML"
            )
        except Exception:
            pass
        return

    won = result["won"]
    icon = "🏆" if won else "💀"
    verdict = "Победа!" if won else "Поражение"

    # Команда игрока
    user_lines = [f"  {RANK_EMOJI.get(uc.rank,'❓')} {uc.character_id} "
                  f"[{LEVEL_LABELS.get(uc.level,'?')}] — {fmt_power(uc.power)}"
                  for uc in result["user_team"][:5]]

    # Команда бота
    bot_lines = []
    for name, bp, lvl in result["bot_cards"]:
        from app.constants.cards import LEVEL_MULTIPLIERS
        eff = int(bp * LEVEL_MULTIPLIERS.get(lvl, 1.0))
        bot_lines.append(f"  🤖 {name} [{LEVEL_LABELS.get(lvl,'?')}] — {fmt_power(eff)}")

    lines = [
        f"{icon} <b>{verdict}!</b>",
        f"🎯 {result['tier_emoji']} {result['tier_name']}",
        f"",
        f"<b>Твоя команда</b> — {fmt_power(result['user_power'])}:",
        *user_lines,
        f"",
        f"<b>Команда бота</b> — {fmt_power(result['bot_power'])}:",
        *bot_lines,
    ]
    if won and result["dust_reward"]:
        lines += ["", f"💎 +{result['dust_reward']} пыли"]

    # КД с разбивкой бонусов
    cd_parts = []
    if result.get("speed_pct"):
        cd_parts.append(f"⚡ мастерство -{result['speed_pct']}%")
    if result.get("donat_pct"):
        cd_parts.append(f"💎 донат -{result['donat_pct']}%")
    if result.get("flow_pct"):
        cd_parts.append(f"🌊 поток -{result['flow_pct']}%")
    cd_bonus = f" ({', '.join(cd_parts)})" if cd_parts else ""
    lines.append(f"⏳ КД: {fmt_ttl(result['cd_seconds'])}{cd_bonus}")

    builder = InlineKeyboardBuilder()
    if result["cd_seconds"] <= 5:
        builder.row(InlineKeyboardButton(
            text=f"🔄 Ещё раз ({result['tier_emoji']})",
            callback_data=f"duel_bot:{tier}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ К дуэлям", callback_data="duel_menu"))

    try:
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        pass


# ── PvP ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "duel_pvp")
async def cb_duel_pvp(cb: CallbackQuery, user: User, state: FSMContext):
    pvp_ttl = await cooldown_service.get_ttl(cooldown_service.duel_pvp_key(user.id))
    if pvp_ttl > 0:
        await cb.answer(f"⏳ КД PvP-дуэли: {fmt_ttl(pvp_ttl)}", show_alert=True)
        return
    await state.set_state(DuelFSM.waiting_opponent)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="duel_menu"))
    try:
        await cb.message.edit_text(
            "⚔️ <b>Дуэль с игроком</b>\n\nВведи <b>@username</b> или <b>tg_id</b>:",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(DuelFSM.waiting_opponent)
async def msg_duel_opponent(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    await state.clear()
    query = message.text.strip().lstrip("@")

    from app.services.admin_service import admin_service
    target = await admin_service.find_user(session, query)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К дуэлям", callback_data="duel_menu"))

    if not target:
        await message.answer("❌ Игрок не найден.", reply_markup=builder.as_markup())
        return

    result = await duel_service.send_challenge(session, user, target)
    await session.commit()

    if not result["ok"]:
        await message.answer(f"❌ {result['reason']}", reply_markup=builder.as_markup())
        return

    # Уведомляем цель
    from app.bot_instance import get_bot
    bot = get_bot()
    challenge_kb = InlineKeyboardBuilder()
    challenge_kb.row(
        InlineKeyboardButton(text="✅ Принять", callback_data="duel_accept"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data="duel_decline"),
    )
    try:
        await bot.send_message(
            target.tg_id,
            f"⚔️ <b>Вызов на дуэль!</b>\n\n"
            f"👤 {html.escape(user.full_name)} вызывает тебя!\n"
            f"⏳ У тебя {result['ttl']} секунд.",
            reply_markup=challenge_kb.as_markup(), parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Вызов отправлен {html.escape(target.full_name)}!\n"
        f"Ждём ответа {result['ttl']} секунд.",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.callback_query(F.data == "duel_accept")
async def cb_duel_accept(cb: CallbackQuery, session: AsyncSession, user: User):
    await cb.answer()
    result = await duel_service.accept_challenge(session, user)
    await session.commit()

    if not result["ok"]:
        try:
            await cb.message.edit_text(f"❌ {result['reason']}", parse_mode="HTML")
        except Exception:
            pass
        return

    from_user = result["from_user"]
    winner = result["winner"]
    dust = result["dust_reward"]
    icon_a = "🏆" if winner.id == from_user.id else "💀"
    icon_b = "🏆" if winner.id == user.id else "💀"

    text = (
        f"⚔️ <b>Результат дуэли!</b>\n\n"
        f"{icon_a} {html.escape(from_user.full_name)} — {fmt_power(result['power_a'])}\n"
        f"{icon_b} {html.escape(user.full_name)} — {fmt_power(result['power_b'])}\n\n"
        f"🏆 Победитель: <b>{html.escape(winner.full_name)}</b>\n"
        f"💎 Награда: +{dust} пыли"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ К дуэлям", callback_data="duel_menu"))

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass

    # Уведомляем инициатора
    from app.bot_instance import get_bot
    try:
        await get_bot().send_message(
            from_user.tg_id, text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "duel_decline")
async def cb_duel_decline(cb: CallbackQuery, user: User):
    declined = await duel_service.decline_challenge(user)
    await cb.answer("Вызов отклонён" if declined else "Вызов уже истёк")
    try:
        await cb.message.edit_text("❌ Вызов отклонён.")
    except Exception:
        pass
