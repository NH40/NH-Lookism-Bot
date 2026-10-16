"""Админка — Роли (клавиатуры)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN, ROLES
from bot.constant.admin.live_config import (
    CB_ROLES_ADD,
    CB_ROLES_DEL_ASK_PREFIX,
    CB_ROLES_DEL_PREFIX,
    CB_ROLES_LIST,
    CB_ROLES_SET_PREFIX,
    CB_ROLES_USER_PREFIX,
)
from bot.texts.admin import BTN_BACK, ROLE_NAMES
from bot.texts.admin.roles_admin import BTN_ADD, BTN_REMOVE, BTN_YES


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def list_menu(staff: list[tuple[int, str | None, str]]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"{ROLE_NAMES.get(role, role)} · {('@' + name) if name else uid}", f"{CB_ROLES_USER_PREFIX}{uid}")] for uid, name, role in staff]
    rows.append([_btn(BTN_ADD, CB_ROLES_ADD)])
    rows.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_menu(uid: int, has_role: bool) -> InlineKeyboardMarkup:
    rows = [[_btn(ROLE_NAMES[r], f"{CB_ROLES_SET_PREFIX}{uid}:{r}") for r in ROLES]]
    if has_role:
        rows.append([_btn(BTN_REMOVE, f"{CB_ROLES_DEL_ASK_PREFIX}{uid}")])
    rows.append([_btn(BTN_BACK, CB_ROLES_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def del_confirm_menu(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_YES, f"{CB_ROLES_DEL_PREFIX}{uid}")], [_btn(BTN_BACK, f"{CB_ROLES_USER_PREFIX}{uid}")]]
    )


def back_to_list() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, CB_ROLES_LIST)]])
