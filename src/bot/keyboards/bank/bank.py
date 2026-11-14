"""Банки игроков и кредиты (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.bank import (
    CB_BANK_CLOSE,
    CB_BANK_CLOSE_YES,
    CB_BANK_CONFIRM,
    CB_BANK_CREATE,
    CB_BANK_DAYS_PREFIX,
    CB_BANK_DEPOSIT,
    CB_BANK_LOANS,
    CB_BANK_MY,
    CB_BANK_OPEN,
    CB_BANK_PAGE_PREFIX,
    CB_BANK_REPAY_ALL_PREFIX,
    CB_BANK_REPAY_PREFIX,
    CB_BANK_TAKE_PREFIX,
    CB_BANK_TERMS,
    CB_BANK_VIEW_PREFIX,
    CB_BANK_WITHDRAW,
)
from bot.constant.common import CB_MENU_SHOP
from bot.texts.bank import (
    BTN_BACK,
    BTN_CLOSE,
    BTN_CLOSE_YES,
    BTN_CONFIRM,
    BTN_CREATE,
    BTN_DEPOSIT,
    BTN_MY_BANK,
    BTN_MY_LOANS,
    BTN_NEXT,
    BTN_PREV,
    BTN_REPAY,
    BTN_REPAY_ALL,
    BTN_TAKE,
    BTN_TERMS,
    BTN_WITHDRAW,
)


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def list_menu(buttons: list[tuple[str, int]], page: int, more: bool) -> InlineKeyboardMarkup:
    kb = [[_b(label, f"{CB_BANK_VIEW_PREFIX}{bank_id}")] for label, bank_id in buttons]
    nav = []
    if page > 0:
        nav.append(_b(BTN_PREV, f"{CB_BANK_PAGE_PREFIX}{page - 1}"))
    if more:
        nav.append(_b(BTN_NEXT, f"{CB_BANK_PAGE_PREFIX}{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append([_b(BTN_MY_LOANS, CB_BANK_LOANS), _b(BTN_MY_BANK, CB_BANK_MY)])
    kb.append([_b(BTN_BACK, CB_MENU_SHOP)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def card_menu(bank_id: int, can_take: bool) -> InlineKeyboardMarkup:
    kb = [[_b(BTN_TAKE, f"{CB_BANK_TAKE_PREFIX}{bank_id}")]] if can_take else []
    kb.append([_b(BTN_BACK, CB_BANK_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def days_menu(min_days: int, max_days: int, bank_id: int) -> InlineKeyboardMarkup:
    days = list(range(min_days, max_days + 1))
    kb = [[_b(str(d), f"{CB_BANK_DAYS_PREFIX}{d}") for d in days[i:i + 6]] for i in range(0, len(days), 6)]
    kb.append([_b(BTN_BACK, f"{CB_BANK_VIEW_PREFIX}{bank_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_menu(bank_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_CONFIRM, CB_BANK_CONFIRM)], [_b(BTN_BACK, f"{CB_BANK_VIEW_PREFIX}{bank_id}")]])


def loans_menu(loan_ids: list[int]) -> InlineKeyboardMarkup:
    kb = [[_b(f"{BTN_REPAY} #{i}", f"{CB_BANK_REPAY_PREFIX}{i}"), _b(f"{BTN_REPAY_ALL} #{i}", f"{CB_BANK_REPAY_ALL_PREFIX}{i}")] for i in loan_ids]
    kb.append([_b(BTN_BACK, CB_BANK_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def my_bank_menu(has_bank: bool) -> InlineKeyboardMarkup:
    if not has_bank:
        return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_CREATE, CB_BANK_CREATE)], [_b(BTN_BACK, CB_BANK_OPEN)]])
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(BTN_DEPOSIT, CB_BANK_DEPOSIT), _b(BTN_WITHDRAW, CB_BANK_WITHDRAW)],
        [_b(BTN_TERMS, CB_BANK_TERMS), _b(BTN_CLOSE, CB_BANK_CLOSE)],
        [_b(BTN_BACK, CB_BANK_OPEN)],
    ])


def close_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_CLOSE_YES, CB_BANK_CLOSE_YES)], [_b(BTN_BACK, CB_BANK_MY)]])


def back_menu(data: str = CB_BANK_OPEN) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_BACK, data)]])


def frozen_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_MY_LOANS, CB_BANK_LOANS)]])
