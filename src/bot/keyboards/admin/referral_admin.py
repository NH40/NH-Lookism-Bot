"""Админка/рефералы: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_REFERRAL
from bot.constant.admin.referral_admin import (
    CB_REF_DELETE_ASK_PREFIX,
    CB_REF_DELETE_PREFIX,
    CB_REF_NEW,
    CB_REF_VIEW_PREFIX,
)
from bot.texts.admin.referral_admin import BTN_BACK, BTN_BACK_LIST, BTN_CONFIRM_DELETE, BTN_DELETE, BTN_NEW

_LIST_CB = f"{CB_ADMIN_SECTION_PREFIX}{SECTION_REFERRAL}"


def _btn(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def list_menu(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[_btn(label, f"{CB_REF_VIEW_PREFIX}{lid}")] for lid, label in items]
    rows.append([_btn(BTN_NEW, CB_REF_NEW)])
    rows.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def detail_menu(link_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_DELETE, f"{CB_REF_DELETE_ASK_PREFIX}{link_id}")],
            [_btn(BTN_BACK_LIST, _LIST_CB)],
        ]
    )


def delete_confirm_menu(link_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_CONFIRM_DELETE, f"{CB_REF_DELETE_PREFIX}{link_id}")],
            [_btn(BTN_BACK, f"{CB_REF_VIEW_PREFIX}{link_id}")],
        ]
    )


def back_to_list() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK_LIST, _LIST_CB)]])
