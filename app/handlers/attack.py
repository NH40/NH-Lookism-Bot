from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.cooldown_service import cooldown_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_ttl
from app.utils.truce import (
    is_truce_active, is_truce_on_cooldown,
    truce_remaining_secs, truce_cd_remaining_secs, truce_button_label,
    TRUCE_DURATION_HOURS, TRUCE_COOLDOWN_HOURS,
)

router = Router()


class AttackFSM(StatesGroup):
    waiting_pvp_choice = State()


async def build_attack_menu(session, user):
    if user.phase == "gang":
        from app.handlers.game.gang import build_gang_menu
        return await build_gang_menu(session, user)
    elif user.phase == "king":
        from app.handlers.game.king import build_king_menu
        return await build_king_menu(session, user)
    elif user.phase == "fist":
        from app.handlers.game.fist import build_fist_menu
        return await build_fist_menu(session, user)
    elif user.phase == "emperor":
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        from app.utils.formatters import fmt_num
        builder = InlineKeyboardBuilder()
        if user.prestige_level < 10:
            builder.row(InlineKeyboardButton(
                text="🌟 Пробудиться", callback_data="do_prestige"
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


@router.callback_query(F.data == "do_prestige")
async def cb_do_prestige(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.prestige_service import prestige_service
    from app.utils.keyboards.common import confirm_kb
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


@router.callback_query(F.data == "truce_menu")
async def cb_truce_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    if is_truce_active(user):
        secs = truce_remaining_secs(user)
        text = (
            f"🕊 <b>Перемирие активно</b>\n\n"
            f"⏱ Осталось: {fmt_ttl(secs)}\n\n"
            f"Ты под защитой — тебя нельзя атаковать.\n"
            f"Но и сам ты не можешь никого атаковать."
        )
        builder.row(InlineKeyboardButton(text="❌ Деактивировать", callback_data="truce_deactivate"))
    elif is_truce_on_cooldown(user):
        secs = truce_cd_remaining_secs(user)
        text = (
            f"⏳ <b>Перезарядка перемирия</b>\n\n"
            f"Следующее перемирие доступно через: {fmt_ttl(secs)}"
        )
    else:
        text = (
            f"🕊 <b>Перемирие</b>\n\n"
            f"⏱ Длительность: {TRUCE_DURATION_HOURS} часов\n"
            f"🔄 Перезарядка: {TRUCE_COOLDOWN_HOURS} часов\n\n"
            f"Во время перемирия ты не можешь атаковать никого,\n"
            f"но и другие игроки не смогут атаковать тебя."
        )
        builder.row(InlineKeyboardButton(text="✅ Активировать", callback_data="truce_confirm"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "truce_confirm")
async def cb_truce_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    if is_truce_active(user) or is_truce_on_cooldown(user):
        await cb.answer("Перемирие недоступно", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Да, активировать", callback_data="truce_activate"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="truce_menu"))
    try:
        await cb.message.edit_text(
            f"🕊 <b>Подтверждение перемирия</b>\n\n"
            f"⏱ Перемирие будет активно <b>{TRUCE_DURATION_HOURS} часов</b>\n"
            f"🔄 После — перезарядка <b>{TRUCE_COOLDOWN_HOURS} часов</b>\n\n"
            f"❗ Во время перемирия ты <b>не сможешь атаковать</b>\n\n"
            f"Активировать перемирие?",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "truce_activate")
async def cb_truce_activate(cb: CallbackQuery, session: AsyncSession, user: User):
    if is_truce_active(user) or is_truce_on_cooldown(user):
        await cb.answer("Перемирие недоступно", show_alert=True)
        return
    now = datetime.now(timezone.utc)
    user.truce_until = now + timedelta(hours=TRUCE_DURATION_HOURS)
    user.truce_cd_until = now + timedelta(hours=TRUCE_DURATION_HOURS + TRUCE_COOLDOWN_HOURS)
    await session.flush()
    try:
        await cb.message.edit_text(
            f"✅ <b>Перемирие активировано!</b>\n\n"
            f"🕊 Ты под защитой на {TRUCE_DURATION_HOURS} часов.\n"
            f"Никто не сможет атаковать тебя,\n"
            f"но и ты не можешь атаковать других.",
            reply_markup=back_kb("attack"),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "truce_deactivate")
async def cb_truce_deactivate(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_truce_active(user):
        await cb.answer("Перемирие не активно", show_alert=True)
        return
    now = datetime.now(timezone.utc)
    user.truce_until = now - timedelta(seconds=1)
    user.truce_cd_until = now + timedelta(hours=TRUCE_COOLDOWN_HOURS)
    await session.flush()
    try:
        await cb.message.edit_text(
            f"❌ <b>Перемирие деактивировано</b>\n\n"
            f"🔄 Следующее перемирие через {TRUCE_COOLDOWN_HOURS} часов.",
            reply_markup=back_kb("attack"),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# Подключаем дочерние роутеры
from app.handlers.game.gang import router as gang_router
from app.handlers.game.king import router as king_router
from app.handlers.game.fist import router as fist_router
from app.handlers.game.king_bots import router as king_bots_router

router.include_router(gang_router)
router.include_router(king_router)
router.include_router(fist_router)
router.include_router(king_bots_router)