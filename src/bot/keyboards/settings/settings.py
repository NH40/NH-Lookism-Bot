"""Настройки (клавиатуры)."""
from __future__ import annotations

from bot.constant.donate import CB_DONATE_OPEN
from bot.texts.donate import BTN_DONATE

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.help import CB_HELP_OPEN
from bot.texts.help import BTN_HELP

from bot.constant.common import CB_MENU_SETTINGS
from bot.constant.gang import CB_GANG_DELETE_ASK
from bot.constant.settings import CB_NOTIFY_ALL_OFF, CB_NOTIFY_ALL_ON, CB_NOTIFY_OPEN, CB_NOTIFY_TOGGLE_PREFIX, NOTIFY_CATEGORIES
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.gang import BTN_DELETE_GANG
from bot.texts.settings import (
    BTN_BACK_TO_SETTINGS,
    BTN_NOTIFICATIONS,
    BTN_NOTIFY_ALL_OFF,
    BTN_NOTIFY_ALL_ON,
    NOTIFY_LABELS,
    NOTIFY_OFF,
    NOTIFY_ON,
)


def settings_menu() -> InlineKeyboardMarkup:
    # Удаление банды — здесь, а не в профиле (пользователь 2026-10-01): необратимое
    # действие не должно стоять среди ежедневной навигации.
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_DONATE, callback_data=CB_DONATE_OPEN)],
            [InlineKeyboardButton(text=BTN_NOTIFICATIONS, callback_data=CB_NOTIFY_OPEN)],
            [InlineKeyboardButton(text=BTN_HELP, callback_data=CB_HELP_OPEN)],
            [InlineKeyboardButton(text=BTN_DELETE_GANG, callback_data=CB_GANG_DELETE_ASK)],
            [InlineKeyboardButton(text=BTN_BACK_TO_PROFILE, callback_data=CB_PROFILE_OPEN)],
        ]
    )


def notifications_menu(muted: set[str]) -> InlineKeyboardMarkup:
    """По кнопке на категорию (✅ включена / 🔕 выключена) + «все разом»."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{NOTIFY_OFF if c in muted else NOTIFY_ON} {NOTIFY_LABELS[c]}",
                callback_data=f"{CB_NOTIFY_TOGGLE_PREFIX}{c}",
            )
        ]
        for c in NOTIFY_CATEGORIES
    ]
    rows.append(
        [
            InlineKeyboardButton(text=BTN_NOTIFY_ALL_ON, callback_data=CB_NOTIFY_ALL_ON),
            InlineKeyboardButton(text=BTN_NOTIFY_ALL_OFF, callback_data=CB_NOTIFY_ALL_OFF),
        ]
    )
    rows.append([InlineKeyboardButton(text=BTN_BACK_TO_SETTINGS, callback_data=CB_MENU_SETTINGS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
