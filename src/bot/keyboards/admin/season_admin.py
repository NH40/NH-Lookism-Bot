"""Админка «Сезон пасса и задания»: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_SEASON
from bot.constant.admin.season_admin import (
    CB_SE_CARD_PREFIX, CB_SE_NEW_ASK, CB_SE_NEW_OK, CB_SE_PLAYER, CB_SE_PREMIUM_PREFIX, CB_SE_QUEST_DONE_PREFIX,
    CB_SE_QUEST_REROLL_ASK_PREFIX, CB_SE_QUEST_REROLL_OK_PREFIX, CB_SE_QUESTS_PREFIX, CB_SE_RESET_ASK_PREFIX,
    CB_SE_RESET_OK_PREFIX, CB_SE_XP_PREFIX,
)
from bot.texts.admin.season_admin import (
    BTN_BACK, BTN_DONE_PREFIX, BTN_GIVE_XP, BTN_NEW_SEASON, BTN_NO, BTN_PLAYER, BTN_QUESTS, BTN_REROLL,
    BTN_RESET_CLAIMS, BTN_TO_PLAYER, BTN_TOGGLE_PREMIUM, BTN_YES,
)


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _m(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_section() -> InlineKeyboardMarkup:
    return _m([[_b(BTN_BACK, f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SEASON}")]])


def menu() -> InlineKeyboardMarkup:
    return _m([[_b(BTN_NEW_SEASON, CB_SE_NEW_ASK)], [_b(BTN_PLAYER, CB_SE_PLAYER)], [_b(BTN_BACK, CB_ADMIN_OPEN)]])


def confirm_new() -> InlineKeyboardMarkup:
    return _m([[_b(BTN_YES, CB_SE_NEW_OK)], [_b(BTN_NO, f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SEASON}")]])


def player_card(uid: int) -> InlineKeyboardMarkup:
    return _m([
        [_b(BTN_GIVE_XP, f"{CB_SE_XP_PREFIX}{uid}")],
        [_b(BTN_TOGGLE_PREMIUM, f"{CB_SE_PREMIUM_PREFIX}{uid}")],
        [_b(BTN_RESET_CLAIMS, f"{CB_SE_RESET_ASK_PREFIX}{uid}")],
        [_b(BTN_QUESTS, f"{CB_SE_QUESTS_PREFIX}{uid}")],
    ] + back_to_section().inline_keyboard)


def to_player(uid: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_TO_PLAYER, f"{CB_SE_CARD_PREFIX}{uid}")]])


def confirm(ok_data: str, back_data: str) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_YES, ok_data)], [_b(BTN_NO, back_data)]])


def confirm_reset(uid: int) -> InlineKeyboardMarkup:
    return confirm(f"{CB_SE_RESET_OK_PREFIX}{uid}", f"{CB_SE_CARD_PREFIX}{uid}")


def confirm_reroll(uid: int) -> InlineKeyboardMarkup:
    return confirm(f"{CB_SE_QUEST_REROLL_OK_PREFIX}{uid}", f"{CB_SE_QUESTS_PREFIX}{uid}")


def quests(uid: int, open_slots: list[int]) -> InlineKeyboardMarkup:
    rows = [[_b(f"{BTN_DONE_PREFIX} #{slot}", f"{CB_SE_QUEST_DONE_PREFIX}{uid}:{slot}")] for slot in open_slots]
    rows.append([_b(BTN_REROLL, f"{CB_SE_QUEST_REROLL_ASK_PREFIX}{uid}")])
    return _m(rows + to_player(uid).inline_keyboard)
