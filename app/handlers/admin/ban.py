"""
Административный модуль бана / разбана игроков.

Поток:
  adm_ban:{tg_id}                  — выбор типа/срока бана
  adm_ban_pick:{tg_id}:{hours|perm} — ввод причины (FSM)
  adm_ban_confirm:{tg_id}:{dur}    — применить бан (из FSM)
  adm_unban:{tg_id}                 — снять бан
"""
import html
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.admin_service import admin_service
from app.handlers.admin._common import is_admin, AdminFSM
from app.utils.formatters import fmt_ttl

router = Router()

# ── Варианты срока бана ───────────────────────────────────────────────────────
# (label, hours | None=permanent)
BAN_OPTIONS: list[tuple[str, int | None]] = [
    ("1 час",     1),
    ("24 часа",   24),
    ("3 дня",     72),
    ("7 дней",    168),
    ("30 дней",   720),
    ("Навсегда",  None),
]


def _dur_label(hours: int | None) -> str:
    if hours is None:
        return "навсегда"
    if hours < 24:
        return f"{hours}ч"
    days = hours // 24
    return f"{days}д"


def _ban_until(hours: int | None) -> datetime | None:
    if hours is None:
        return None
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# ── Шаг 1: выбор длительности ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_ban:"))
async def cb_adm_ban(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    ban_status = ""
    if getattr(found, "is_banned", False):
        ban_until = getattr(found, "ban_until", None)
        if ban_until is None:
            ban_status = "\n⛔ <b>Уже забанен навсегда</b>"
        else:
            secs = max(0, int((ban_until - datetime.now(timezone.utc)).total_seconds()))
            ban_status = f"\n⛔ <b>Уже забанен, осталось {fmt_ttl(secs)}</b>"

    builder = InlineKeyboardBuilder()
    for label, hours in BAN_OPTIONS:
        dur_str = "perm" if hours is None else str(hours)
        builder.row(InlineKeyboardButton(
            text=f"🔨 {label}",
            callback_data=f"adm_ban_pick:{tg_id}:{dur_str}",
        ))
    builder.row(InlineKeyboardButton(
        text="✅ Разбанить",
        callback_data=f"adm_unban:{tg_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"adm_user:{tg_id}",
    ))

    reason = getattr(found, "ban_reason", None) or "—"
    text = (
        f"🔨 <b>Бан игрока</b>\n"
        f"👤 {html.escape(found.full_name)}\n"
        f"🆔 <code>{found.tg_id}</code>"
        f"{ban_status}\n"
        f"📝 Причина бана: {html.escape(reason)}\n\n"
        f"Выбери срок:"
    )
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 2: ввод причины (FSM) ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_ban_pick:"))
async def cb_adm_ban_pick(cb: CallbackQuery, user: User, state: FSMContext):
    if not is_admin(user.tg_id):
        return
    parts = cb.data.split(":")
    tg_id = int(parts[1])
    dur = parts[2]  # "perm" | "1" | "24" | ...

    await state.set_state(AdminFSM.waiting_ban_reason)
    await state.update_data(ban_tg_id=tg_id, ban_dur=dur)

    hours = None if dur == "perm" else int(dur)
    dur_label = "навсегда" if hours is None else _dur_label(hours)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Отмена",
        callback_data=f"adm_ban:{tg_id}",
    ))
    try:
        await cb.message.edit_text(
            f"🔨 Бан на <b>{dur_label}</b>\n\n"
            f"Введи причину бана (или «—» чтобы не указывать):",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Шаг 3: применить бан ─────────────────────────────────────────────────────

@router.message(AdminFSM.waiting_ban_reason)
async def msg_ban_reason(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    if not is_admin(user.tg_id):
        await state.clear()
        return

    data = await state.get_data()
    await state.clear()

    tg_id: int = data.get("ban_tg_id")
    dur: str = data.get("ban_dur", "perm")

    reason = message.text.strip()
    if reason == "—":
        reason = None

    hours = None if dur == "perm" else int(dur)
    ban_until = _ban_until(hours)
    dur_label = "навсегда" if hours is None else _dur_label(hours)

    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await message.answer("❌ Игрок не найден")
        return

    # Применяем бан
    found.is_banned = True
    found.ban_until = ban_until
    found.ban_reason = reason
    await session.flush()

    # Сброс кэша карточки
    from app.handlers.admin._common import invalidate_admin_card_cache
    await invalidate_admin_card_cache(found.tg_id)

    # Уведомляем забаненного
    try:
        from app.bot_instance import get_bot
        bot = get_bot()
        if bot:
            ban_text = (
                f"🚫 <b>Вы заблокированы</b>\n\n"
                f"Срок: <b>{dur_label}</b>\n"
                + (f"Причина: {html.escape(reason)}\n" if reason else "")
                + "\nПо вопросам обращайтесь к администрации."
            )
            await bot.send_message(found.tg_id, ban_text, parse_mode="HTML")
    except Exception:
        pass

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ К игроку",
        callback_data=f"adm_user:{tg_id}",
    ))
    await message.answer(
        f"✅ <b>Бан применён</b>\n\n"
        f"👤 {html.escape(found.full_name)} (<code>{found.tg_id}</code>)\n"
        f"⏱ Срок: <b>{dur_label}</b>\n"
        + (f"📝 Причина: {html.escape(reason)}" if reason else "📝 Причина: не указана"),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Разбан ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_unban:"))
async def cb_adm_unban(cb: CallbackQuery, session: AsyncSession, user: User):
    if not is_admin(user.tg_id):
        return
    tg_id = int(cb.data.split(":")[1])
    found = await admin_service.find_user(session, str(tg_id))
    if not found:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    if not getattr(found, "is_banned", False):
        await cb.answer("Игрок не забанен", show_alert=True)
        return

    found.is_banned = False
    found.ban_until = None
    found.ban_reason = None
    await session.flush()

    from app.handlers.admin._common import invalidate_admin_card_cache
    await invalidate_admin_card_cache(found.tg_id)

    # Уведомляем игрока
    try:
        from app.bot_instance import get_bot
        bot = get_bot()
        if bot:
            await bot.send_message(
                found.tg_id,
                "✅ <b>Ваш бан снят.</b>\nДобро пожаловать обратно!",
                parse_mode="HTML",
            )
    except Exception:
        pass

    await cb.answer("✅ Игрок разбанен", show_alert=True)

    # Обновляем карточку
    from app.handlers.admin._common import _show_user_card
    await _show_user_card(cb.message, session, found)
