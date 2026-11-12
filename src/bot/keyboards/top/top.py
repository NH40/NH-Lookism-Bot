"""Топ игроков/кланов и список игроков (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_NOOP
from bot.constant.top import CB_PLAYERS_PAGE_PREFIX, CB_TOP_PREFIX, TAB_CLANS, TAB_PLAYERS
from bot.texts.top import BTN_ALL_PLAYERS, BTN_TAB_CLANS, BTN_TAB_PLAYERS, BTN_TO_TOP


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def top_menu(tab: str, league: int | None = None) -> InlineKeyboardMarkup:
    from bot.config.league import LEAGUES

    def tab_btn(code: str, label: str) -> InlineKeyboardButton:
        return _btn(f"• {label} •" if code == tab else label, f"{CB_TOP_PREFIX}{code}")

    rows = [[tab_btn(TAB_PLAYERS, BTN_TAB_PLAYERS), tab_btn(TAB_CLANS, BTN_TAB_CLANS)]]
    if tab == TAB_PLAYERS:  # вкладки лиг (2026-11-12); «Все» — общий топ, по нему награды
        leagues = [_btn("• Все •" if league is None else "Все", f"{CB_TOP_PREFIX}{TAB_PLAYERS}")]
        leagues += [
            _btn(f"• {x.name} •" if league == x.index else x.name, f"{CB_TOP_PREFIX}{TAB_PLAYERS}:{x.index}") for x in LEAGUES
        ]
        rows += [leagues[i : i + 3] for i in range(0, len(leagues), 3)]
    rows.append([_btn(BTN_ALL_PLAYERS, f"{CB_PLAYERS_PAGE_PREFIX}0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
