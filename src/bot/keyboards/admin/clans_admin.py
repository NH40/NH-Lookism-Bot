"""Админка «Кланы»: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_CLANS
from bot.constant.admin.clans_admin import (
    CB_C_COOLDOWN_PREFIX, CB_C_DELETE_OK_PREFIX, CB_C_DELETE_PREFIX, CB_C_DONATE_PREFIX, CB_C_FIND, CB_C_LANDS_PREFIX,
    CB_C_SHIELD_PREFIX, CB_C_TRANSFER_OK_PREFIX, CB_C_TRANSFER_PICK_PREFIX, CB_C_TRANSFER_PREFIX,
    CB_C_TREASURY_PREFIX, CB_C_VIEW_PREFIX,
)
from bot.texts.admin.clans_admin import (
    BTN_BACK, BTN_COOLDOWN, BTN_DELETE, BTN_DONATE, BTN_FIND, BTN_LANDS, BTN_NO, BTN_SHIELD, BTN_TO_CLAN,
    BTN_TRANSFER, BTN_TREASURY, BTN_YES,
)


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _m(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_section() -> InlineKeyboardMarkup:
    return _m([[_b(BTN_BACK, f"{CB_ADMIN_SECTION_PREFIX}{SECTION_CLANS}")]])


def menu() -> InlineKeyboardMarkup:
    from bot.constant.admin import CB_ADMIN_OPEN

    return _m([[_b(BTN_FIND, CB_C_FIND)], [_b(BTN_BACK, CB_ADMIN_OPEN)]])


def pick_clans(clans: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    return _m([[_b(name, f"{CB_C_VIEW_PREFIX}{cid}")] for cid, name in clans] + back_to_section().inline_keyboard)


def clan_card(clan_id: int) -> InlineKeyboardMarkup:
    return _m([
        [_b(BTN_TRANSFER, f"{CB_C_TRANSFER_PREFIX}{clan_id}")],
        [_b(BTN_LANDS, f"{CB_C_LANDS_PREFIX}{clan_id}"), _b(BTN_TREASURY, f"{CB_C_TREASURY_PREFIX}{clan_id}")],
        [_b(BTN_DONATE, f"{CB_C_DONATE_PREFIX}{clan_id}")],
        [_b(BTN_SHIELD, f"{CB_C_SHIELD_PREFIX}{clan_id}"), _b(BTN_COOLDOWN, f"{CB_C_COOLDOWN_PREFIX}{clan_id}")],
        [_b(BTN_DELETE, f"{CB_C_DELETE_PREFIX}{clan_id}")],
    ] + back_to_section().inline_keyboard)


def to_clan(clan_id: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_TO_CLAN, f"{CB_C_VIEW_PREFIX}{clan_id}")]])


def pick_owner(clan_id: int, members: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[_b(label, f"{CB_C_TRANSFER_PICK_PREFIX}{clan_id}:{uid}")] for uid, label in members]
    return _m(rows + to_clan(clan_id).inline_keyboard)


def confirm_transfer(clan_id: int, user_id: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_YES, f"{CB_C_TRANSFER_OK_PREFIX}{clan_id}:{user_id}")], [_b(BTN_NO, f"{CB_C_TRANSFER_PREFIX}{clan_id}")]])


def confirm_delete(clan_id: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_YES, f"{CB_C_DELETE_OK_PREFIX}{clan_id}")], [_b(BTN_NO, f"{CB_C_VIEW_PREFIX}{clan_id}")]])
