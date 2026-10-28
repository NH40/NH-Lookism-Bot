"""Казино (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.casino import (
    CASINO_STAKE_RESOURCES,
    CB_BJ_DOUBLE,
    CB_BJ_HIT,
    CB_BJ_STAND,
    CB_CASINO_GAME_PREFIX,
    CB_CASINO_OPEN,
    CB_CASINO_SQUAD_PREFIX,
    CB_CASINO_STAKE_PREFIX,
    CB_CASINO_STATISTS_PREFIX,
    CB_SLOTS_AGAIN_PREFIX,
    GAME_BLACKJACK,
    GAME_SLOTS,
)
from bot.constant.common import CB_MENU_SHOP
from bot.constant.poker import CB_POKER_OPEN
from bot.texts.casino import (
    BTN_BJ_AGAIN,
    BTN_BJ_DOUBLE,
    BTN_BJ_HIT,
    BTN_BJ_STAND,
    BTN_POKER,
    BTN_SLOTS_AGAIN,
    BTN_SQUAD,
    BTN_STAKE_STATISTS,
    GAME_NAMES,
)
from bot.texts.common import BTN_BACK
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def casino_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(GAME_NAMES[GAME_SLOTS], f"{CB_CASINO_GAME_PREFIX}{GAME_SLOTS}"),
                _btn(GAME_NAMES[GAME_BLACKJACK], f"{CB_CASINO_GAME_PREFIX}{GAME_BLACKJACK}"),
            ],
            [_btn(BTN_POKER, CB_POKER_OPEN)],
            [_btn(BTN_BACK, CB_MENU_SHOP)],
        ]
    )


def stake_menu(game: str) -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_CASINO_STAKE_PREFIX}{game}:{code}") for code in CASINO_STAKE_RESOURCES]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    if game == GAME_BLACKJACK:
        rows.append([_btn(BTN_STAKE_STATISTS, f"{CB_CASINO_STATISTS_PREFIX}{game}")])
    rows.append([_btn(BTN_BACK, CB_CASINO_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def squads_menu(game: str, squads: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_SQUAD.format(title=title, total=format_number(total)), f"{CB_CASINO_SQUAD_PREFIX}{game}:{key}")]
        for key, title, total in squads
    ]
    rows.append([_btn(BTN_BACK, f"{CB_CASINO_GAME_PREFIX}{game}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_game(game: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, f"{CB_CASINO_GAME_PREFIX}{game}")]])


def slots_result_menu(resource: str, amount: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_SLOTS_AGAIN.format(stake=amount_label(resource, amount)), f"{CB_SLOTS_AGAIN_PREFIX}{resource}:{amount}")],
            [_btn(BTN_BACK, f"{CB_CASINO_GAME_PREFIX}{GAME_SLOTS}")],
        ]
    )


def blackjack_menu(can_double: bool) -> InlineKeyboardMarkup:
    row = [_btn(BTN_BJ_HIT, CB_BJ_HIT), _btn(BTN_BJ_STAND, CB_BJ_STAND)]
    if can_double:
        row.append(_btn(BTN_BJ_DOUBLE, CB_BJ_DOUBLE))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def blackjack_done_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_BJ_AGAIN, f"{CB_CASINO_GAME_PREFIX}{GAME_BLACKJACK}")],
            [_btn(BTN_BACK, CB_CASINO_OPEN)],
        ]
    )
