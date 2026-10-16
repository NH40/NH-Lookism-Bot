"""Ежедневные задания (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.quest import CB_QUEST_ADMIN_COMPLETE
from bot.texts.quest import BTN_ADMIN_COMPLETE
from bot.constant.battle_pass import CB_BP_OPEN
from bot.constant.common import CB_MENU_QUESTS
from bot.constant.profile import CB_PROFILE_OPEN
from bot.constant.quest import CB_QUEST_REROLL_ALL, CB_QUEST_SCROLL, CB_QUEST_SCROLL_PREFIX, CB_QUEST_SWAP_MENU, CB_QUEST_SWAP_PREFIX
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.quest import (
    BTN_BACK_TO_QUESTS,
    BTN_BATTLE_PASS,
    BTN_REROLL_ALL,
    BTN_SCROLL,
    BTN_SWAP,
)


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def quests_menu(*, reroll_all: bool, swap: bool, admin: bool = False) -> InlineKeyboardMarkup:
    rows = []
    actions = ([_btn(BTN_REROLL_ALL, CB_QUEST_REROLL_ALL)] if reroll_all else []) + (
        [_btn(BTN_SWAP, CB_QUEST_SWAP_MENU)] if swap else []
    )
    if actions:
        rows.append(actions)
    rows.append([_btn(BTN_BATTLE_PASS, CB_BP_OPEN), _btn(BTN_SCROLL, CB_QUEST_SCROLL)])
    if admin:
        rows.append([_btn(BTN_ADMIN_COMPLETE, CB_QUEST_ADMIN_COMPLETE)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def swap_menu(options: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[_btn(label, f"{CB_QUEST_SWAP_PREFIX}{slot}")] for slot, label in options]
    rows.append([_btn(BTN_BACK_TO_QUESTS, CB_MENU_QUESTS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def scroll_menu(options: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"📜 {label}", f"{CB_QUEST_SCROLL_PREFIX}{quest_id}")] for quest_id, label in options]
    rows.append([_btn(BTN_BACK_TO_QUESTS, CB_MENU_QUESTS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
