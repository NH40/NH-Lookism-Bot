"""Админка «События карты»: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN
from bot.constant.admin.events_admin import (
    CB_E_CODE_PREFIX, CB_E_GO_PREFIX, CB_E_KIND_PREFIX, CB_E_LIST, CB_E_RM_ASK_PREFIX, CB_E_RM_OK_PREFIX,
    CB_E_SPAWN, CB_E_VIEW_PREFIX,
)
from bot.texts.admin.events_admin import (
    BTN_BACK, BTN_NO, BTN_NO_PUSH, BTN_PUSH, BTN_REFRESH, BTN_REMOVE, BTN_SPAWN, BTN_YES, KIND_TITLES,
)


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _m(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu(events: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[_b(title, f"{CB_E_VIEW_PREFIX}{eid}")] for eid, title in events]
    rows.append([_b(BTN_SPAWN, CB_E_SPAWN), _b(BTN_REFRESH, CB_E_LIST)])
    rows.append([_b(BTN_BACK, CB_ADMIN_OPEN)])
    return _m(rows)


def event_card(event_id: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_REMOVE, f"{CB_E_RM_ASK_PREFIX}{event_id}")], [_b(BTN_BACK, CB_E_LIST)]])


def confirm_remove(event_id: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_YES, f"{CB_E_RM_OK_PREFIX}{event_id}")], [_b(BTN_NO, f"{CB_E_VIEW_PREFIX}{event_id}")]])


def spawn_kinds() -> InlineKeyboardMarkup:
    rows = [[_b(title, f"{CB_E_KIND_PREFIX}{key}")] for key, title in KIND_TITLES.items()]
    rows.append([_b(BTN_BACK, CB_E_LIST)])
    return _m(rows)


def spawn_codes(kind_key: str, titles: list[str]) -> InlineKeyboardMarkup:
    rows = [[_b(title, f"{CB_E_CODE_PREFIX}{kind_key}:{i}")] for i, title in enumerate(titles)]
    rows.append([_b(BTN_BACK, CB_E_SPAWN)])
    return _m(rows)


def spawn_push(kind_key: str, idx: int) -> InlineKeyboardMarkup:
    return _m([
        [_b(BTN_PUSH, f"{CB_E_GO_PREFIX}{kind_key}:{idx}:1")],
        [_b(BTN_NO_PUSH, f"{CB_E_GO_PREFIX}{kind_key}:{idx}:0")],
        [_b(BTN_BACK, f"{CB_E_KIND_PREFIX}{kind_key}")],
    ])
