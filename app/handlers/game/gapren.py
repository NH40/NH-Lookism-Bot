from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.game.gapren import get_or_create_challenge, gapren_power, attack_gapren
from app.config.game_balance import GAPREN_WINS_NEEDED
from app.utils.formatters import fmt_num, fmt_ttl

router = Router()


async def _build_awakening_screen(session: AsyncSession, user: User) -> tuple[str, any]:
    challenge = await get_or_create_challenge(session, user.id)
    now = datetime.now(timezone.utc)
    on_cd = challenge.cooldown_until and challenge.cooldown_until > now

    builder = InlineKeyboardBuilder()

    if challenge.streak >= GAPREN_WINS_NEEDED:
        text = (
            f"🌟 <b>Пробуждения</b>\n\n"
            f"🐉 Гапрён повержен трижды подряд!\n"
            f"Пробуждение открыто.\n\n"
            f"Уровень пробуждения: {user.prestige_level}/10"
        )
        builder.row(InlineKeyboardButton(text="🌟 Пробудиться", callback_data="do_prestige"))
    else:
        next_power = gapren_power(user, challenge.streak)
        text = (
            f"🌟 <b>Пробуждения</b>\n\n"
            f"Победи Гапрёна {GAPREN_WINS_NEEDED} раза <b>подряд</b>, чтобы открыть пробуждение.\n"
            f"Поражение сбрасывает серию!\n\n"
            f"🏆 Серия побед: <b>{challenge.streak}/{GAPREN_WINS_NEEDED}</b>\n"
            f"💪 Твоя мощь: <b>{fmt_num(user.combat_power)}</b>\n"
            f"👹 Мощь Гапрёна: <b>{fmt_num(next_power)}</b>"
        )
        if on_cd:
            secs = int((challenge.cooldown_until - now).total_seconds())
            builder.row(InlineKeyboardButton(
                text=f"⏳ КД: {fmt_ttl(secs)}", callback_data="gapren_cd",
            ))
        else:
            builder.row(InlineKeyboardButton(text="⚔️ Атаковать Гапрёна", callback_data="gapren_attack"))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="emperor_gangs"))
    return text, builder.as_markup()


@router.callback_query(F.data == "emperor_awakening")
async def cb_emperor_awakening(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "emperor":
        await cb.answer("Только для Императора!", show_alert=True)
        return
    text, kb = await _build_awakening_screen(session, user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "gapren_cd")
async def cb_gapren_cd(cb: CallbackQuery, session: AsyncSession, user: User):
    challenge = await get_or_create_challenge(session, user.id)
    now = datetime.now(timezone.utc)
    if challenge.cooldown_until and challenge.cooldown_until > now:
        secs = int((challenge.cooldown_until - now).total_seconds())
        await cb.answer(f"⏳ Перезарядка: {fmt_ttl(secs)}", show_alert=True)
    else:
        await cb.answer("Можно атаковать!")


@router.callback_query(F.data == "gapren_attack")
async def cb_gapren_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.phase != "emperor":
        await cb.answer("Только для Императора!", show_alert=True)
        return

    from app.services.cooldown_service import cooldown_service
    lock_key = f"gapren_attack:{user.id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=15):
        await cb.answer("⏳ Атака уже обрабатывается", show_alert=True)
        return

    try:
        result = await attack_gapren(session, user)
        if not result["ok"]:
            await cb.answer(result["reason"], show_alert=True)
            return

        lines = [f"🐉 <b>Бой с Гапрёном</b>\n"]
        lines.append(f"💪 Твоя мощь: {fmt_num(result['user_power'])}")
        lines.append(f"👹 Мощь Гапрёна: {fmt_num(result['opponent_power'])}\n")

        if result["win"]:
            if result["unlocked"]:
                lines.append("🏆 <b>ПОБЕДА! Серия 3/3 — Гапрён повержен!</b>")
                lines.append("🌟 Пробуждение открыто!")
            else:
                lines.append(f"🏆 <b>ПОБЕДА!</b> Серия: {result['streak']}/{GAPREN_WINS_NEEDED}")
                lines.append("Атакуй ещё раз, чтобы продолжить серию!")
        else:
            lines.append("💀 <b>ПОРАЖЕНИЕ.</b> Серия сброшена — начинай с первого боя!")

        builder = InlineKeyboardBuilder()
        if result["unlocked"]:
            builder.row(InlineKeyboardButton(text="🌟 Пробудиться", callback_data="do_prestige"))
        builder.row(InlineKeyboardButton(text="◀️ К пробуждению", callback_data="emperor_awakening"))

        text = "\n".join(lines)
        try:
            await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
        await cb.answer()
    finally:
        await cooldown_service.release_lock(lock_key)
