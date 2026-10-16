"""Контракты статистов (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_SHOP
from bot.constant.contract import CB_CONTRACT_BUY_PREFIX, CB_CONTRACT_OPEN, CB_CONTRACT_PAGE_PREFIX, CB_CONTRACT_RANK_PREFIX
from bot.texts.common import BTN_BACK
from bot.texts.contract import BTN_CONFIRM_BUY, BTN_CONTRACT_NEXT, BTN_CONTRACT_PREV, BTN_CONTRACT_RANK
from bot.utils.formatting import format_number

_PER_ROW = 3


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def ranks_menu(ranks: list[tuple[str, int]], page: int, pages: int) -> InlineKeyboardMarkup:
    """Сетка рангов страницы (ранг · цена бойца), листание к слабым/сильным рангам."""
    buttons = [
        _btn(BTN_CONTRACT_RANK.format(rank=rank, price=format_number(price)), f"{CB_CONTRACT_RANK_PREFIX}{rank}")
        for rank, price in ranks
    ]
    rows = [buttons[i:i + _PER_ROW] for i in range(0, len(buttons), _PER_ROW)]
    nav = []
    if page > 0:
        nav.append(_btn(BTN_CONTRACT_PREV, f"{CB_CONTRACT_PAGE_PREFIX}{page - 1}"))
    if page < pages - 1:
        nav.append(_btn(BTN_CONTRACT_NEXT, f"{CB_CONTRACT_PAGE_PREFIX}{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(BTN_BACK, CB_MENU_SHOP)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_contracts() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, CB_CONTRACT_OPEN)]])


def confirm_menu(rank: str, quantity: int, total: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_CONFIRM_BUY.format(total=format_number(total)), f"{CB_CONTRACT_BUY_PREFIX}{rank}:{quantity}")],
            [_btn(BTN_BACK, CB_CONTRACT_OPEN)],
        ]
    )
