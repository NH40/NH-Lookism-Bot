"""Банки игроков и кредиты (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.bank import (
    CB_BANK_APPROVE_PREFIX,
    CB_BANK_APPROVE_TERMS_PREFIX,
    CB_BANK_APPS,
    CB_BANK_CANCEL_PREFIX,
    CB_BANK_CLOSE,
    CB_BANK_CLOSE_YES,
    CB_BANK_CONFIRM,
    CB_BANK_CREATE,
    CB_BANK_DAYS_PREFIX,
    CB_BANK_DECLINE_PREFIX,
    CB_BANK_DEPOSIT,
    CB_BANK_LOANS,
    CB_BANK_MEMBER_ADD,
    CB_BANK_MEMBER_DEL_PREFIX,
    CB_BANK_MEMBERS,
    CB_BANK_MY,
    CB_BANK_OPEN,
    CB_BANK_PAGE_PREFIX,
    CB_BANK_REJECT_PREFIX,
    CB_BANK_REPAY_ALL_PREFIX,
    CB_BANK_REPAY_PREFIX,
    CB_BANK_SIGN_PREFIX,
    CB_BANK_TAKE_PREFIX,
    CB_BANK_TERMS,
    CB_BANK_VIEW_PREFIX,
    CB_BANK_WITHDRAW,
)
from bot.constant.common import CB_MENU_SHOP
from bot.texts.bank import (
    BTN_APPROVE,
    BTN_APPROVE_TERMS,
    BTN_APPS,
    BTN_BACK,
    BTN_CANCEL_APP,
    BTN_CLOSE,
    BTN_CLOSE_YES,
    BTN_CREATE,
    BTN_DECLINE,
    BTN_DEPOSIT,
    BTN_KIND,
    BTN_MEMBER_ADD,
    BTN_MEMBERS,
    BTN_MY_BANK,
    BTN_MY_LOANS,
    BTN_NEXT,
    BTN_PREV,
    BTN_REJECT,
    BTN_REPAY,
    BTN_REPAY_ALL,
    BTN_SEND,
    BTN_SIGN,
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


def card_menu(bank_id: int, kinds: list[str]) -> InlineKeyboardMarkup:
    kb = [[_b(BTN_KIND[k], f"{CB_BANK_TAKE_PREFIX}{bank_id}:{k}") for k in kinds]] if kinds else []
    kb.append([_b(BTN_BACK, CB_BANK_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def days_menu(min_days: int, max_days: int, bank_id: int) -> InlineKeyboardMarkup:
    days = list(range(min_days, max_days + 1))
    kb = [[_b(str(d), f"{CB_BANK_DAYS_PREFIX}{d}") for d in days[i:i + 6]] for i in range(0, len(days), 6)]
    kb.append([_b(BTN_BACK, f"{CB_BANK_VIEW_PREFIX}{bank_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_menu(bank_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_SEND, CB_BANK_CONFIRM)], [_b(BTN_BACK, f"{CB_BANK_VIEW_PREFIX}{bank_id}")]])


def loans_menu(open_ids: list[int], pending_ids: list[int], offered_ids: list[int]) -> InlineKeyboardMarkup:
    kb = [[_b(f"{BTN_REPAY} #{i}", f"{CB_BANK_REPAY_PREFIX}{i}"), _b(f"{BTN_REPAY_ALL} #{i}", f"{CB_BANK_REPAY_ALL_PREFIX}{i}")] for i in open_ids]
    kb += [[_b(f"{BTN_SIGN} #{i}", f"{CB_BANK_SIGN_PREFIX}{i}"), _b(f"{BTN_DECLINE} #{i}", f"{CB_BANK_DECLINE_PREFIX}{i}")] for i in offered_ids]
    kb += [[_b(f"{BTN_CANCEL_APP} #{i}", f"{CB_BANK_CANCEL_PREFIX}{i}")] for i in pending_ids]
    kb.append([_b(BTN_BACK, CB_BANK_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def offer_menu(loan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_SIGN, f"{CB_BANK_SIGN_PREFIX}{loan_id}"), _b(BTN_DECLINE, f"{CB_BANK_DECLINE_PREFIX}{loan_id}")]])


def app_menu(loan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(BTN_APPROVE, f"{CB_BANK_APPROVE_PREFIX}{loan_id}"), _b(BTN_REJECT, f"{CB_BANK_REJECT_PREFIX}{loan_id}")],
        [_b(BTN_APPROVE_TERMS, f"{CB_BANK_APPROVE_TERMS_PREFIX}{loan_id}")],
    ])


def apps_menu(ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for i in ids:
        kb.append([_b(f"{BTN_APPROVE} #{i}", f"{CB_BANK_APPROVE_PREFIX}{i}"), _b(f"{BTN_REJECT} #{i}", f"{CB_BANK_REJECT_PREFIX}{i}")])
        kb.append([_b(f"{BTN_APPROVE_TERMS} #{i}", f"{CB_BANK_APPROVE_TERMS_PREFIX}{i}")])
    kb.append([_b(BTN_BACK, CB_BANK_MY)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def my_bank_menu(has_bank: bool, is_owner: bool, apps: int) -> InlineKeyboardMarkup:
    if not has_bank:
        return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_CREATE, CB_BANK_CREATE)], [_b(BTN_BACK, CB_BANK_OPEN)]])
    kb = [[_b(f"{BTN_APPS} ({apps})" if apps else BTN_APPS, CB_BANK_APPS), _b(BTN_DEPOSIT, CB_BANK_DEPOSIT)]]
    if is_owner:
        kb.append([_b(BTN_WITHDRAW, CB_BANK_WITHDRAW), _b(BTN_TERMS, CB_BANK_TERMS)])
        kb.append([_b(BTN_MEMBERS, CB_BANK_MEMBERS), _b(BTN_CLOSE, CB_BANK_CLOSE)])
    kb.append([_b(BTN_BACK, CB_BANK_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def members_menu(members: list[tuple[int, str]], can_add: bool) -> InlineKeyboardMarkup:
    kb = [[_b(f"✖️ {name}", f"{CB_BANK_MEMBER_DEL_PREFIX}{uid}")] for uid, name in members]
    if can_add:
        kb.append([_b(BTN_MEMBER_ADD, CB_BANK_MEMBER_ADD)])
    kb.append([_b(BTN_BACK, CB_BANK_MY)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def close_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_CLOSE_YES, CB_BANK_CLOSE_YES)], [_b(BTN_BACK, CB_BANK_MY)]])


def back_menu(data: str = CB_BANK_OPEN) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_BACK, data)]])


def frozen_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_MY_LOANS, CB_BANK_LOANS)]])
