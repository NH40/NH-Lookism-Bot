from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.keyboards.common import back_kb

router = Router()


@router.callback_query(F.data == "ui_settings")
async def cb_ui_settings(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.ultra_instinct and not user.true_ultra_instinct and user.ui_level == 0 and not user.ui_is_donat:
        await cb.message.edit_text(
            "👁 <b>Ультра Инстинкт</b>\n\n"
            "❌ Не активирован\n\n"
            "Получи УИ в разделе <b>Рейды → Крафт</b>\n"
            "или купи донат-титул UI",
            reply_markup=back_kb("skills"),
            parse_mode="HTML",
        )
        return

    builder = InlineKeyboardBuilder()

    has_1 = user.ui_level >= 1 or user.ui_is_donat
    has_2 = user.ui_level >= 2 or user.ui_is_donat
    has_3 = user.ui_level >= 3 or user.ui_is_donat
    has_4 = user.ui_level >= 4 or user.ui_is_donat

    if has_1:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_recruit else '❌'} Авто-вербовка",
            callback_data="toggle_ui_recruit"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-вербовка (УИ I)",
            callback_data="noop"
        ))

    if has_2:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_train else '❌'} Авто-тренировка",
            callback_data="toggle_ui_train"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-тренировка (УИ II)",
            callback_data="noop"
        ))

    if has_3:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_ticket else '❌'} Авто-тикеты",
            callback_data="toggle_ui_ticket"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-тикеты (УИ III)",
            callback_data="noop"
        ))

    if has_4:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_pull else '❌'} Авто-прокрутка персонажей",
            callback_data="toggle_ui_pull"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-прокрутка (УИ IV)",
            callback_data="noop"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    ui_level_str = "Донат (макс)" if user.ui_is_donat else f"Уровень {user.ui_level}/4"
    tui_str = " | TUI 🔱" if user.true_ultra_instinct else ""

    text = (
        f"👁 <b>Ультра Инстинкт</b> — {ui_level_str}{tui_str}\n\n"
        f"Настройки автоматизации:\n"
        f"{'✅' if has_1 else '🔒'} Авто-вербовка" + (f": {'✅' if user.ui_auto_recruit else '❌'}" if has_1 else " (УИ I)") + "\n"
        + f"{'✅' if has_2 else '🔒'} Авто-тренировка" + (f": {'✅' if user.ui_auto_train else '❌'}" if has_2 else " (УИ II)") + "\n"
        + f"{'✅' if has_3 else '🔒'} Авто-тикеты" + (f": {'✅' if user.ui_auto_ticket else '❌'}" if has_3 else " (УИ III)") + "\n"
        + f"{'✅' if has_4 else '🔒'} Авто-прокрутка" + (f": {'✅' if user.ui_auto_pull else '❌'}" if has_4 else " (УИ IV)")
    )

    try:
        await cb.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "toggle_ui_recruit")
async def toggle_ui_recruit(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 1 and not user.ui_is_donat:
        await cb.answer("Нужен УИ I уровня!", show_alert=True)
        return
    user.ui_auto_recruit = not user.ui_auto_recruit
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_train")
async def toggle_ui_train(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 2 and not user.ui_is_donat:
        await cb.answer("Нужен УИ II уровня!", show_alert=True)
        return
    user.ui_auto_train = not user.ui_auto_train
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_ticket")
async def toggle_ui_ticket(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 3 and not user.ui_is_donat:
        await cb.answer("Нужен УИ III уровня!", show_alert=True)
        return
    user.ui_auto_ticket = not user.ui_auto_ticket
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_pull")
async def toggle_ui_pull(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 4 and not user.ui_is_donat:
        await cb.answer("Нужен УИ IV уровня!", show_alert=True)
        return
    user.ui_auto_pull = not user.ui_auto_pull
    await session.flush()
    await cb_ui_settings(cb, session, user)


