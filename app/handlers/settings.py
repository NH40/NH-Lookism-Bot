from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_power

router = Router()

GAME_VERSION = "1.0.1"


class SettingsFSM(StatesGroup):
    waiting_gang_name = State()


@router.callback_query(F.data == "settings")
async def cb_settings(cb: CallbackQuery, session: AsyncSession, user: User):
    user.settings_opened += 1
    await session.flush()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Мой профиль",        callback_data="profile"))
    builder.row(InlineKeyboardButton(text="✏️ Сменить название банды", callback_data="change_gang_name"))
    notif_text = f"🔔 Уведомления: {'ВКЛ' if user.notifications_enabled else 'ВЫКЛ'}"
    builder.row(InlineKeyboardButton(text=notif_text,              callback_data="toggle_notifications"))
    builder.row(InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="referral_info"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",              callback_data="main_menu"))

    await cb.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"🏴 Название банды: {user.gang_name or 'не задано'}\n"
        f"🔔 Уведомления: {'ВКЛ' if user.notifications_enabled else 'ВЫКЛ'}\n"
        f"🔖 Версия: {GAME_VERSION}\n\n"
        f"Выбери действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "referral_info")
async def cb_referral_info(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.referral_service import referral_service
    students = await referral_service.get_students(session, user.id)

    ref_link = f"https://t.me/lookism_batlle_bot?start=ref_{user.tg_id}"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К настройкам", callback_data="settings"))

    students_str = ""
    if students:
        students_str = f"\n\nТвои ученики ({len(students)}):\n"
        for s in students[:5]:
            students_str += f"  • {s.full_name} | {fmt_power(s.combat_power)}\n"
        if len(students) > 5:
            students_str += f"  ...ещё {len(students)-5}"

    await cb.message.edit_text(
        f"🔗 <b>Система Учитель / Ученик</b>\n\n"
        f"Твоя ссылка учителя:\n"
        f"<code>{ref_link}</code>\n\n"
        f"{'─'*20}\n\n"
        f"Как работает система:\n\n"
        f"🏆 <b>Учитель получает:</b>\n"
        f"  • +1,000 NHCoin при регистрации ученика\n"
        f"  • 3% от дохода каждого ученика\n\n"
        f"🥇 <b>Ученик получает:</b>\n"
        f"  • +2,000 NHCoin при регистрации\n"
        f"  • +5% от боевой мощи учителя"
        + students_str,
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "change_gang_name")
async def cb_change_gang_name(
    cb: CallbackQuery, session: AsyncSession,
    user: User, state: FSMContext
):
    await state.set_state(SettingsFSM.waiting_gang_name)
    await cb.message.edit_text(
        "✏️ Введите новое название банды (до 32 символов):",
        reply_markup=back_kb("settings"),
    )


@router.message(SettingsFSM.waiting_gang_name)
async def msg_gang_name(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    name = message.text.strip()[:32]
    if not name:
        await message.answer("Название не может быть пустым")
        return
    user.gang_name = name
    await session.flush()
    await state.clear()
    await message.answer(
        f"✅ Название банды изменено на: <b>{name}</b>",
        reply_markup=back_kb("settings"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "toggle_notifications")
async def cb_toggle_notifications(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    user.notifications_enabled = not user.notifications_enabled
    await session.flush()
    await cb_settings(cb, session, user)