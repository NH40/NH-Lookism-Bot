import random
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.emperor_gang import EmperorGangRecord
from app.constants.emperor import (
    EMPEROR_GANGS, EMPEROR_GANG_MAP,
    GANG_COOLDOWN_HOURS, GANG_STRENGTH_GROWTH,
)
from app.utils.formatters import fmt_num, fmt_ttl

router = Router()

# ── Вспомогательные ───────────────────────────────────────────────────────────

async def _get_record(
    session: AsyncSession, user_id: int, gang_id: str
) -> EmperorGangRecord | None:
    return await session.scalar(
        select(EmperorGangRecord).where(
            EmperorGangRecord.user_id == user_id,
            EmperorGangRecord.gang_id == gang_id,
        )
    )


def _gang_power(cfg, defeat_count: int) -> int:
    """Мощь группировки с учётом роста после каждой победы (+20%)."""
    return int(cfg.base_power * ((1 + GANG_STRENGTH_GROWTH) ** defeat_count))


async def _build_gang_list(session: AsyncSession, user: User) -> tuple[str, any]:
    now = datetime.now(timezone.utc)
    builder = InlineKeyboardBuilder()

    lines = [f"⚔️ <b>Группировки Императора</b>\n"]

    for cfg in EMPEROR_GANGS:
        rec = await _get_record(session, user.id, cfg.gang_id)
        defeat_count = rec.defeat_count if rec else 0
        cooldown_until = rec.cooldown_until if rec else None

        power = _gang_power(cfg, defeat_count)
        on_cd = cooldown_until and cooldown_until > now

        if on_cd:
            secs = int((cooldown_until - now).total_seconds())
            status_icon = "🔒"
            btn_text = f"{cfg.emoji} {cfg.name} | ⏳ {fmt_ttl(secs)}"
            cd_data = f"emperor_gang_cd:{cfg.gang_id}"
            builder.row(InlineKeyboardButton(text=btn_text, callback_data=cd_data))
        else:
            can_win = user.combat_power >= power
            can_icon = "✅" if can_win else "❌"
            streak = f" [+{defeat_count * 20}%]" if defeat_count > 0 else ""
            btn_text = f"{cfg.emoji} {cfg.name}{streak} | {fmt_num(power)} | {can_icon}"
            builder.row(InlineKeyboardButton(
                text=btn_text,
                callback_data=f"emperor_gang_info:{cfg.gang_id}"
            ))

    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    text = (
        f"⚔️ <b>Группировки Императора</b>\n\n"
        f"💪 Ваша мощь: <b>{fmt_num(user.combat_power)}</b>\n\n"
        f"Побеждайте группировки — они усиливаются на <b>20%</b> после каждого поражения.\n"
        f"Перезарядка: <b>{GANG_COOLDOWN_HOURS} час</b>"
    )
    return text, builder.as_markup()


# ── Главное меню Emperor (вместо экрана пробуждения) ─────────────────────────

@router.callback_query(F.data == "emperor_gangs")
async def cb_emperor_gangs(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "emperor":
        await cb.answer("Только для Императора!", show_alert=True)
        return
    text, kb = await _build_gang_list(session, user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        # Сообщение — фото (результат боя с карточкой) — удаляем и присылаем текст
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


# ── Информация о группировке ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emperor_gang_info:"))
async def cb_emperor_gang_info(cb: CallbackQuery, session: AsyncSession, user: User):
    gang_id = cb.data.split(":")[1]
    cfg = EMPEROR_GANG_MAP.get(gang_id)
    if not cfg:
        await cb.answer("Группировка не найдена", show_alert=True)
        return

    rec = await _get_record(session, user.id, gang_id)
    defeat_count = rec.defeat_count if rec else 0
    power = _gang_power(cfg, defeat_count)
    now = datetime.now(timezone.utc)

    on_cd = rec and rec.cooldown_until and rec.cooldown_until > now
    if on_cd:
        secs = int((rec.cooldown_until - now).total_seconds())
        await cb.answer(f"⏳ Перезарядка: {fmt_ttl(secs)}", show_alert=True)
        return

    can_win = user.combat_power >= power
    can_icon = "✅" if can_win else "⚠️"

    members_str = "\n".join(f"  • {m}" for m in cfg.members)
    growth_str = f" (×{(1 + GANG_STRENGTH_GROWTH) ** defeat_count:.2f} от базы)" if defeat_count > 0 else ""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"⚔️ Атаковать",
        callback_data=f"emperor_gang_attack:{gang_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="emperor_gangs"
    ))

    try:
        await cb.message.edit_text(
            f"{cfg.emoji} <b>{cfg.name}</b>\n\n"
            f"{cfg.desc}\n\n"
            f"👥 Состав:\n{members_str}\n\n"
            f"💪 Мощь: <b>{fmt_num(power)}</b>{growth_str}\n"
            f"🏆 Побед: <b>{defeat_count}</b>\n\n"
            f"🎁 Награда:\n"
            f"  💰 {fmt_num(cfg.reward_coins_min)}–{fmt_num(cfg.reward_coins_max)} монет\n"
            f"  🃏 Шанс карточки: {cfg.drop_chance}%\n\n"
            f"{can_icon} Ваша мощь: {fmt_num(user.combat_power)} / {fmt_num(power)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("emperor_gang_cd:"))
async def cb_emperor_gang_cd(cb: CallbackQuery, session: AsyncSession, user: User):
    gang_id = cb.data.split(":")[1]
    rec = await _get_record(session, user.id, gang_id)
    now = datetime.now(timezone.utc)
    if rec and rec.cooldown_until and rec.cooldown_until > now:
        secs = int((rec.cooldown_until - now).total_seconds())
        await cb.answer(f"⏳ Перезарядка: {fmt_ttl(secs)}", show_alert=True)
    else:
        await cb.answer("Можно атаковать!")


# ── Атака ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emperor_gang_attack:"))
async def cb_emperor_gang_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "emperor":
        await cb.answer("Только для Императора!", show_alert=True)
        return

    gang_id = cb.data.split(":")[1]
    cfg = EMPEROR_GANG_MAP.get(gang_id)
    if not cfg:
        await cb.answer("Группировка не найдена", show_alert=True)
        return

    now = datetime.now(timezone.utc)

    # Получаем или создаём запись
    rec = await _get_record(session, user.id, gang_id)
    if not rec:
        rec = EmperorGangRecord(user_id=user.id, gang_id=gang_id, defeat_count=0)
        session.add(rec)
        await session.flush()

    # Проверяем КД
    if rec.cooldown_until and rec.cooldown_until > now:
        secs = int((rec.cooldown_until - now).total_seconds())
        await cb.answer(f"⏳ КД: {fmt_ttl(secs)}", show_alert=True)
        return

    gang_power = _gang_power(cfg, rec.defeat_count)

    # Боевая мощь с учётом зелий
    from app.services.combat_service import get_effective_power
    user_power = await get_effective_power(session, user)

    # Шанс победы: ratio-based, минимум 10%, максимум 90%
    ratio = user_power / gang_power
    win_chance = min(90, max(10, int(ratio * 60)))
    won = random.randint(1, 100) <= win_chance

    result_lines = [f"{cfg.emoji} <b>Бой: {cfg.name}</b>\n"]
    result_lines.append(f"💪 Ваша мощь: {fmt_num(user_power)}")
    result_lines.append(f"👊 Мощь врага: {fmt_num(gang_power)}\n")

    dropped_char: dict | None = None  # карточка для отправки фото

    if won:
        # Начисляем монеты
        coins_reward = random.randint(cfg.reward_coins_min, cfg.reward_coins_max)
        user.nh_coins += coins_reward
        result_lines.append(f"🏆 <b>ПОБЕДА!</b>")
        result_lines.append(f"💰 +{fmt_num(coins_reward)} монет")

        # Шанс карточки — только из состава группировки
        got_card = random.randint(1, 100) <= cfg.drop_chance
        if got_card:
            from app.data.characters import CHARACTERS, RANK_EMOJI
            candidates = [c for c in CHARACTERS if c["name"] in cfg.members]
            if candidates:
                char = random.choice(candidates)
                from app.models.character import UserCharacter
                from app.constants.cards import LEVEL_MULTIPLIERS
                level = 0
                base_power = char["power"]
                power_val = int(base_power * LEVEL_MULTIPLIERS[level])
                new_char = UserCharacter(
                    user_id=user.id,
                    character_id=char["name"],
                    rank=char["rank"],
                    base_power=base_power,
                    power=power_val,
                    level=level,
                )
                session.add(new_char)
                from app.repositories.squad_repo import squad_repo
                await squad_repo.update_user_combat_power(session, user)
                rank_emoji = RANK_EMOJI.get(char["rank"], "⭐")
                result_lines.append(f"🃏 Дроп: {rank_emoji} <b>{char['name']}</b>")
                dropped_char = char

        # Обновляем запись: +1 победа, ставим КД
        rec.defeat_count += 1
        rec.cooldown_until = now + timedelta(hours=GANG_COOLDOWN_HOURS)
        new_power = _gang_power(cfg, rec.defeat_count)
        result_lines.append(f"\n💹 Группировка усилилась до {fmt_num(new_power)} (+20%)")
        result_lines.append(f"⏳ КД: {GANG_COOLDOWN_HOURS} час")

        await session.flush()

    else:
        result_lines.append(f"💀 <b>ПОРАЖЕНИЕ</b>")
        result_lines.append(f"Группировка оказалась сильнее. Прокачайся и попробуй снова!")

    text = "\n".join(result_lines)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ К группировкам", callback_data="emperor_gangs"
    ))
    kb = builder.as_markup()

    # Если выпала карточка — пробуем отправить фото
    if dropped_char:
        from app.bot_instance import get_bot
        from app.utils.card_sender import send_card_photo
        bot = get_bot()
        sent = await send_card_photo(
            bot=bot,
            chat_id=cb.message.chat.id,
            char_name=dropped_char["name"],
            caption=text,
            reply_markup=kb,
        )
        if sent:
            # Удаляем предыдущее сообщение (меню атаки)
            try:
                await cb.message.delete()
            except Exception:
                pass
            await cb.answer()
            return

    # Карточки нет или фото не нашлось — просто редактируем текст
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()
