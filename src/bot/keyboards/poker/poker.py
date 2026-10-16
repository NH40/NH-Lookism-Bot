"""PvP-покер (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.poker import POKER_BUY_INS, POKER_MAX_PLAYERS, POKER_MIN_PLAYERS, POKER_WAIT_OPTIONS_SECONDS
from bot.constant.casino import CB_CASINO_OPEN
from bot.constant.poker import (
    ACT_CALL,
    ACT_CHECK,
    ACT_FOLD,
    ACT_RAISE,
    CB_POKER_ACT_PREFIX,
    CB_POKER_CREATE,
    CB_POKER_CREATE_PREFIX,
    CB_POKER_JOIN_PREFIX,
    CB_POKER_LEAVE_PREFIX,
    CB_POKER_OPEN,
    CB_POKER_VIEW_PREFIX,
)
from bot.texts.common import BTN_BACK
from bot.texts.poker import (
    BTN_ALL_IN,
    BTN_BUY_IN,
    BTN_CALL,
    BTN_CHECK,
    BTN_CREATE,
    BTN_FOLD,
    BTN_JOIN,
    BTN_LEAVE,
    BTN_MY_TABLE,
    BTN_PLAYERS,
    BTN_RAISE_MIN,
    BTN_RAISE_POT,
    BTN_REFRESH,
    BTN_WAIT,
)
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def lobby_menu(tables: list, my_table: int | None) -> InlineKeyboardMarkup:
    rows = []
    if my_table:
        rows.append([_btn(BTN_MY_TABLE, f"{CB_POKER_VIEW_PREFIX}{my_table}")])
    else:
        rows.extend(
            [_btn(BTN_JOIN.format(id=t.id, buy_in=format_number(t.buy_in), players=t.players, max=t.max_players), f"{CB_POKER_JOIN_PREFIX}{t.id}")]
            for t in tables
        )
        rows.append([_btn(BTN_CREATE, CB_POKER_CREATE)])
    rows.append([_btn(BTN_REFRESH, CB_POKER_OPEN), _btn(BTN_BACK, CB_CASINO_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def buy_in_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(BTN_BUY_IN.format(buy_in=format_number(b)), f"{CB_POKER_CREATE_PREFIX}{b}") for b in POKER_BUY_INS]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([_btn(BTN_BACK, CB_POKER_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def players_menu(buy_in: int) -> InlineKeyboardMarkup:
    row = [_btn(BTN_PLAYERS.format(n=n), f"{CB_POKER_CREATE_PREFIX}{buy_in}:{n}") for n in range(POKER_MIN_PLAYERS, POKER_MAX_PLAYERS + 1)]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:], [_btn(BTN_BACK, CB_POKER_CREATE)]])


def wait_menu(buy_in: int, players: int) -> InlineKeyboardMarkup:
    row = [_btn(BTN_WAIT.format(minutes=s // 60), f"{CB_POKER_CREATE_PREFIX}{buy_in}:{players}:{s}") for s in POKER_WAIT_OPTIONS_SECONDS]
    return InlineKeyboardMarkup(inline_keyboard=[row, [_btn(BTN_BACK, f"{CB_POKER_CREATE_PREFIX}{buy_in}")]])


def table_menu(table_id: int, hand_no: int, *, my_turn: bool, call: int, min_raise: int, pot_raise: int, all_in: int,
               can_raise: bool, closed: bool = False) -> InlineKeyboardMarkup:
    rows = []
    act = f"{CB_POKER_ACT_PREFIX}{table_id}:{hand_no}"
    if my_turn:
        rows.append([
            _btn(BTN_FOLD, f"{act}:{ACT_FOLD}:0"),
            _btn(BTN_CALL.format(amount=format_number(call)), f"{act}:{ACT_CALL}:0") if call else _btn(BTN_CHECK, f"{act}:{ACT_CHECK}:0"),
        ])
        if can_raise:
            raises = [_btn(BTN_RAISE_MIN.format(amount=format_number(min_raise)), f"{act}:{ACT_RAISE}:{min_raise}")]
            if pot_raise > min_raise and pot_raise < all_in:
                raises.append(_btn(BTN_RAISE_POT.format(amount=format_number(pot_raise)), f"{act}:{ACT_RAISE}:{pot_raise}"))
            rows.append(raises)
            rows.append([_btn(BTN_ALL_IN.format(amount=format_number(all_in)), f"{act}:{ACT_RAISE}:{all_in}")])
    if closed:
        rows.append([_btn(BTN_BACK, CB_POKER_OPEN)])
    else:
        rows.append([_btn(BTN_REFRESH, f"{CB_POKER_VIEW_PREFIX}{table_id}"), _btn(BTN_LEAVE, f"{CB_POKER_LEAVE_PREFIX}{table_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
