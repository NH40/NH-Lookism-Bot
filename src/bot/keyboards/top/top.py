"""Топ игроков/кланов и список игроков (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_NOOP
from bot.constant.top import CB_PLAYERS_PAGE_PREFIX, CB_TOP_PREFIX, TAB_CLANS, TAB_PLAYERS
from bot.texts.top import BTN_ALL_PLAYERS, BTN_TAB_CLANS, BTN_TAB_PLAYERS, BTN_TO_TOP


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def top_menu(tab: str) -> InlineKeyboardMarkup:
    def tab_btn(code: str, label: str) -> InlineKeyboardButton:
        return _btn(f"• {label} •" if code == tab else label, f"{CB_TOP_PREFIX}{code}")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [tab_btn(TAB_PLAYERS, BTN_TAB_PLAYERS), tab_btn(TAB_CLANS, BTN_TAB_CLANS)],
            [_btn(BTN_ALL_PLAYERS, f"{CB_PLAYERS_PAGE_PREFIX}0")],
        ]
    )


def players_menu(page: int, pages: int) -> InlineKeyboardMarkup:
    rows = []
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(_btn("◀️", f"{CB_PLAYERS_PAGE_PREFIX}{page - 1}"))
        nav.append(_btn(f"{page + 1}/{pages}", CB_NOOP))
        if page < pages - 1:
            nav.append(_btn("▶️", f"{CB_PLAYERS_PAGE_PREFIX}{page + 1}"))
        rows.append(nav)
    rows.append([_btn(BTN_TO_TOP, f"{CB_TOP_PREFIX}{TAB_PLAYERS}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
