"""Уникальные техники и учителя (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.training import CB_TRAIN_TECH_VIEW_PREFIX
from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.constant.event import CB_EVENT_CONNECT_PREFIX
from bot.constant.map import CB_MAP_OPEN
from bot.constant.unique_technique import (
    CB_TECH_ACTIVATE_PREFIX,
    CB_TECH_CLAIM_PREFIX,
    CB_TECH_OPEN,
    CB_TECH_VIEW_PREFIX,
)
from bot.texts.development import BTN_BACK_TO_DEVELOPMENT
from bot.texts.unique_technique import (
    BTN_ACTIVATE,
    BTN_BACK_TO_MAP,
    BTN_BACK_TO_TECHNIQUES,
    BTN_CLAIM,
    BTN_CLAIM_QUEST,
    BTN_CONNECT,
    BTN_LEVEL_UP,
    BTN_TECH_ITEM,
    MARK_ACTIVE,
    MARK_OWNED,
    TECHNIQUE_NAMES,
)
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def teacher_menu(event_id: int, code: str, *, can_connect: bool, can_claim: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_connect:
        rows.append([_btn(BTN_CONNECT, f"{CB_EVENT_CONNECT_PREFIX}{event_id}")])
    if can_claim:
        rows.append([_btn(BTN_CLAIM, f"{CB_TECH_CLAIM_PREFIX}{code}")])
    rows.append([_btn(BTN_BACK_TO_MAP, CB_MAP_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def techniques_menu(owned: dict[str, int], active: str | None, claimable: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        _btn(
            BTN_TECH_ITEM.format(mark=MARK_ACTIVE if c == active else MARK_OWNED, name=TECHNIQUE_NAMES[c], level=lv),
            f"{CB_TECH_VIEW_PREFIX}{c}",
        )
        for c, lv in owned.items()
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.extend([_btn(BTN_CLAIM_QUEST.format(technique=TECHNIQUE_NAMES[c]), f"{CB_TECH_CLAIM_PREFIX}{c}")] for c in claimable)
    rows.append([_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def technique_detail_menu(code: str, *, cost: int | None, is_active: bool) -> InlineKeyboardMarkup:
    rows = []
    if cost is not None:
        rows.append([_btn(BTN_LEVEL_UP.format(cost=format_number(cost)), f"{CB_TRAIN_TECH_VIEW_PREFIX}{code}")])
    if not is_active:
        rows.append([_btn(BTN_ACTIVATE, f"{CB_TECH_ACTIVATE_PREFIX}{code}")])
    rows.append([_btn(BTN_BACK_TO_TECHNIQUES, CB_TECH_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
