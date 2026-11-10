"""Админка — Настройки на лету (клавиатуры). В callback_data — короткий id ключа (`live_config.sid`):
имена констант длинные, а предел Telegram — 64 байта."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN
from bot.constant.admin.live_config import (
    CB_CONFIG_DUR_PREFIX,
    CB_CONFIG_KEY_PREFIX,
    CB_CONFIG_LIST,
    CB_CONFIG_RESET_PREFIX,
    CB_CONFIG_SECTION_PREFIX,
    CB_CONFIG_SET_PREFIX,
    CONFIG_DURATIONS,
)
from bot.texts.admin import BTN_BACK
from bot.texts.admin.live_config import BTN_CHANGE, BTN_CHANGED, BTN_RESET, BTN_SECTION

KEYS_PER_PAGE = 8


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def sections_menu(sections: list[tuple[str, str, int]], changed: int, changed_code: str) -> InlineKeyboardMarkup:
    """(код, название, сколько настроек)."""
    buttons = [_btn(BTN_SECTION.format(title=title, count=count), f"{CB_CONFIG_SECTION_PREFIX}{code}:0") for code, title, count in sections]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    if changed:
        keyboard.append([_btn(BTN_CHANGED.format(count=changed), f"{CB_CONFIG_SECTION_PREFIX}{changed_code}:0")])
    keyboard.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def subsections_menu(subs: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """Подразделы раздела: по одному в строке — названия длинные."""
    keyboard = [[_btn(BTN_SECTION.format(title=title, count=count), f"{CB_CONFIG_SECTION_PREFIX}{code}:0")] for code, title, count in subs]
    keyboard.append([_btn(BTN_BACK, CB_CONFIG_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def list_menu(section: str, rows: list[tuple[str, str]], page: int, pages: int, *, back: str = CB_CONFIG_LIST) -> InlineKeyboardMarkup:
    """rows: [(короткий id, подпись)] — только текущая страница."""
    keyboard = [[_btn(label, f"{CB_CONFIG_KEY_PREFIX}{short}")] for short, label in rows]
    if pages > 1:
        nav = [_btn("◀️", f"{CB_CONFIG_SECTION_PREFIX}{section}:{page - 1}")] if page > 0 else []
        nav.append(_btn(f"{page + 1}/{pages}", f"{CB_CONFIG_SECTION_PREFIX}{section}:{page}"))
        if page < pages - 1:
            nav.append(_btn("▶️", f"{CB_CONFIG_SECTION_PREFIX}{section}:{page + 1}"))
        keyboard.append(nav)
    keyboard.append([_btn(BTN_BACK, back)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def key_menu(short: str, section: str, page: int, overridden: bool) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_CHANGE, f"{CB_CONFIG_SET_PREFIX}{short}")]]
    if overridden:
        rows.append([_btn(BTN_RESET, f"{CB_CONFIG_RESET_PREFIX}{short}")])
    rows.append([_btn(BTN_BACK, f"{CB_CONFIG_SECTION_PREFIX}{section}:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def duration_menu(short: str) -> InlineKeyboardMarkup:
    row = [_btn(label, f"{CB_CONFIG_DUR_PREFIX}{short}:{hours}") for hours, label in CONFIG_DURATIONS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:], [_btn(BTN_BACK, f"{CB_CONFIG_KEY_PREFIX}{short}")]])


def back_to_key(short: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, f"{CB_CONFIG_KEY_PREFIX}{short}")]])
