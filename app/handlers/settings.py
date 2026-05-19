from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.game_version import GameVersion
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, fmt_power

router = Router()

DEFAULT_VERSION = "1.0.0"


class SettingsFSM(StatesGroup):
    waiting_gang_name = State()


async def get_current_version(session: AsyncSession) -> str:
    result = await session.execute(
        select(GameVersion)
        .order_by(GameVersion.applied_at.desc())
        .limit(1)
    )
    gv = result.scalar_one_or_none()
    return gv.version if gv else DEFAULT_VERSION


@router.callback_query(F.data == "settings")
async def cb_settings(cb: CallbackQuery, session: AsyncSession, user: User):
    user.settings_opened += 1
    await session.flush()

    version = await get_current_version(session)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📊 Мой профиль", callback_data="profile"
    ))
    builder.row(InlineKeyboardButton(
        text="✏️ Сменить название банды", callback_data="change_gang_name"
    ))
    builder.row(InlineKeyboardButton(
        text="🔔 Уведомления", callback_data="notifications_menu"
    ))
    builder.row(InlineKeyboardButton(
        text="🔗 Реферальная ссылка", callback_data="referral_info"
    ))
    builder.row(InlineKeyboardButton(
        text="💀 Удалить банду", callback_data="delete_gang_confirm"
    ))
    builder.row(InlineKeyboardButton(
        text="📖 Гайд", callback_data="guide"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="main_menu"
    ))

    master = "ВКЛ" if user.notifications_enabled else "ВЫКЛ"
    await cb.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"🏴 Название банды: {user.gang_name or 'не задано'}\n"
        f"🔔 Уведомления: {master}\n"
        f"🔖 Версия: {version}\n\n"
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
    builder.row(InlineKeyboardButton(
        text="◀️ К настройкам", callback_data="settings"
    ))

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


def _notif_icon(enabled: bool) -> str:
    return "🔔" if enabled else "🔕"


def _on_off(enabled: bool) -> str:
    return "ВКЛ" if enabled else "ВЫКЛ"


@router.callback_query(F.data == "notifications_menu")
async def cb_notifications_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    master = user.notifications_enabled
    pvp = getattr(user, "notif_pvp", True)
    auction = getattr(user, "notif_auction", True)
    cities = getattr(user, "notif_cities", True)
    clan_war = getattr(user, "notif_clan_war", True)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"{'🔔' if master else '🔕'} Все уведомления: {_on_off(master)}",
        callback_data="toggle_notif:master"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{'─' * 20}", callback_data="noop"
    ))
    if master:
        builder.row(InlineKeyboardButton(
            text=f"{_notif_icon(pvp)} ⚔️ PvP атаки: {_on_off(pvp)}",
            callback_data="toggle_notif:pvp"
        ))
        builder.row(InlineKeyboardButton(
            text=f"{_notif_icon(auction)} 🏆 Аукционы: {_on_off(auction)}",
            callback_data="toggle_notif:auction"
        ))
        builder.row(InlineKeyboardButton(
            text=f"{_notif_icon(cities)} 🏙 Прогресс городов: {_on_off(cities)}",
            callback_data="toggle_notif:cities"
        ))
        builder.row(InlineKeyboardButton(
            text=f"{_notif_icon(clan_war)} 🏯 Клановые войны: {_on_off(clan_war)}",
            callback_data="toggle_notif:clan_war"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="settings"))

    lines = [
        f"🔔 <b>Настройки уведомлений</b>\n",
        f"Мастер: <b>{_on_off(master)}</b>",
    ]
    if master:
        lines += [
            f"",
            f"⚔️ PvP атаки: <b>{_on_off(pvp)}</b>",
            f"🏆 Аукционы: <b>{_on_off(auction)}</b>",
            f"🏙 Прогресс городов: <b>{_on_off(cities)}</b>",
            f"🏯 Клановые войны: <b>{_on_off(clan_war)}</b>",
        ]
    else:
        lines.append(f"\n<i>Включи мастер-переключатель чтобы настроить категории</i>")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("toggle_notif:"))
async def cb_toggle_notif(cb: CallbackQuery, session: AsyncSession, user: User):
    key = cb.data.split(":")[1]
    if key == "master":
        user.notifications_enabled = not user.notifications_enabled
    elif key == "pvp":
        user.notif_pvp = not getattr(user, "notif_pvp", True)
    elif key == "auction":
        user.notif_auction = not getattr(user, "notif_auction", True)
    elif key == "cities":
        user.notif_cities = not getattr(user, "notif_cities", True)
    elif key == "clan_war":
        user.notif_clan_war = not getattr(user, "notif_clan_war", True)
    await session.flush()
    await cb_notifications_menu(cb, session, user)

@router.callback_query(F.data == "delete_gang_confirm")
async def cb_delete_gang_confirm(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Да, удалить", callback_data="delete_gang_do"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data="settings"
    ))
    await cb.message.edit_text(
        "💀 <b>Удаление банды</b>\n\n"
        "Весь прогресс будет сброшен!\n"
        "Донаты и пробуждения сохранятся.\n\n"
        "Подтвердить?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "delete_gang_do")
async def cb_delete_gang_do(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.prestige_service import prestige_service
    from app.services.raid_service import raid_service as rs
    
    # keep_ui=False — удаление банды сбрасывает УИ и фрагменты
    await prestige_service._reset_progress(session, user, keep_ui=False)
    
    # Принудительно сбрасываем УИ если нет доната
    if not user.ui_is_donat:
        user.ultra_instinct = False
        user.true_ultra_instinct = False
        user.ui_level = 0
        user.ui_fragments = 0
        user.ui_auto_recruit = False
        user.ui_auto_train = False
        user.ui_auto_ticket = False
        user.ui_auto_pull = False
        await session.flush()
    
    await cb.message.edit_text(
        "💀 <b>Банда удалена.</b>\n\nНачинай сначала!",
        reply_markup=back_kb("main_menu"),
        parse_mode="HTML",
    )