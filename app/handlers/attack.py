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
        # Софтлок-фикс: _check_emperor_eligibility иначе срабатывает только
        # как побочный эффект ПОБЕДЫ в атаке/битве за трон. Король, который
        # уже владеет (сам + вассалы) всеми городами страны, но которому
        # больше некого атаковать (все свободны/его, других королей не
        # осталось) — никогда не совершает такое действие и застревает
        # Королём навсегда, хотя формально уже выполнил условие Императора
        # (см. репорт "захватила все города, а Императором не стала").
        # Поэтому проверяем пассивно при каждом открытии меню атаки.
        from app.services.game_service import game_service
        promo = await game_service._check_emperor_eligibility(session, user)
        if promo and promo.get("promoted"):
            from app.utils.keyboards.common import back_kb
            return f"🎉 {promo['message']}", back_kb("main_menu"), None
        from app.handlers.game.king import build_king_menu
        return await build_king_menu(session, user)
    elif user.phase == "emperor":
        from app.handlers.game.emperor import _build_gang_list
        text, kb = await _build_gang_list(session, user)
        return text, kb, None
    return "⚔️ Атака недоступна", back_kb("main_menu"), None


@router.callback_query(F.data == "attack")
async def cb_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    # Проверка кредитной блокировки
    from app.services.bank.credits_service import credits_service
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        from app.utils.keyboards.common import back_kb
        from app.utils.menu_media import safe_edit
        await safe_edit(cb, block_msg, back_kb("bank_credits"))
        await cb.answer()
        return

    text, kb, photo = await build_attack_menu(session, user)
    from app.utils.menu_media import send_menu
    await send_menu(cb, text, kb, photo)
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

    from sqlalchemy import select
    from app.models.gapren import GaprenChallenge
    from app.config.game_balance import GAPREN_WINS_NEEDED
    challenge = await session.scalar(
        select(GaprenChallenge).where(GaprenChallenge.user_id == user.id)
    )
    if not challenge or challenge.streak < GAPREN_WINS_NEEDED:
        await cb.answer(
            "Сначала победи Гапрёна 3 раза подряд (Император → Атака → Пробуждения)!",
            show_alert=True,
        )
        return
    from app.utils.menu_media import send_menu
    await send_menu(
        cb,
        f"🌟 <b>Пробуждение</b>\n\n"
        f"Уровень: {user.prestige_level}/10\n\n"
        f"После пробуждения:\n"
        f"✅ +5% к боевой мощи навсегда\n"
        f"✅ +5% к доходу навсегда\n"
        f"✅ +1% к шансу тикета навсегда\n\n"
        f"❌ Весь прогресс будет сброшен!\n"
        f"(донаты и пробуждения сохраняются)\n\n"
        f"Подтвердить?",
        confirm_kb("prestige_confirm", "attack"),
    )


@router.callback_query(F.data == "prestige_confirm")
async def cb_prestige_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.prestige_service import prestige_service
    result = await prestige_service.do_prestige(session, user)
    if result["ok"]:
        from app.utils.menu_media import send_menu
        await send_menu(
            cb,
            f"🌟 <b>Пробуждение {result['level']}/10!</b>\n\n"
            f"Прогресс сброшен. Начинай снова!",
            back_kb("main_menu"),
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
    from app.utils.menu_media import send_menu
    await send_menu(cb, text, builder.as_markup())
    await cb.answer()


@router.callback_query(F.data == "truce_confirm")
async def cb_truce_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    if is_truce_active(user) or is_truce_on_cooldown(user):
        await cb.answer("Перемирие недоступно", show_alert=True)
        return
    from app.utils.keyboards.common import confirm_kb
    from app.utils.menu_media import send_menu
    await send_menu(
        cb,
        f"🕊 <b>Подтверждение перемирия</b>\n\n"
        f"⏱ Перемирие будет активно <b>{TRUCE_DURATION_HOURS} часов</b>\n"
        f"🔄 После — перезарядка <b>{TRUCE_COOLDOWN_HOURS} часов</b>\n\n"
        f"❗ Во время перемирия ты <b>не сможешь атаковать</b>\n\n"
        f"Активировать перемирие?",
        confirm_kb("truce_activate", "truce_menu"),
    )
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
    from app.utils.menu_media import send_menu
    await send_menu(
        cb,
        f"✅ <b>Перемирие активировано!</b>\n\n"
        f"🕊 Ты под защитой на {TRUCE_DURATION_HOURS} часов.\n"
        f"Никто не сможет атаковать тебя,\n"
        f"но и ты не можешь атаковать других.",
        back_kb("attack"),
    )
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
    from app.utils.menu_media import send_menu
    await send_menu(
        cb,
        f"❌ <b>Перемирие деактивировано</b>\n\n"
        f"🔄 Следующее перемирие через {TRUCE_COOLDOWN_HOURS} часов.",
        back_kb("attack"),
    )
    await cb.answer()


# Подключаем дочерние роутеры
from app.handlers.game.gang import router as gang_router
from app.handlers.game.king import router as king_router
from app.handlers.game.emperor import router as emperor_router
from app.handlers.game.gapren import router as gapren_router

router.include_router(gang_router)
router.include_router(king_router)
router.include_router(emperor_router)
router.include_router(gapren_router)