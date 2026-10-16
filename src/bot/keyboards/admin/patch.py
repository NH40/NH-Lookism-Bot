"""Админка — Патч и вайп (клавиатуры)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_PATCH
from bot.constant.admin.live_config import (
    CB_PATCH_PATCH_INFO,
    CB_PATCH_PATCH_STEP1,
    CB_PATCH_PATCH_STEP2,
    CB_PATCH_WIPE_INFO,
    CB_PATCH_WIPE_STEP1,
    CB_PATCH_WIPE_STEP2,
)
from bot.texts.admin import BTN_BACK
from bot.texts.admin.patch import BTN_PATCH, BTN_STEP1, BTN_STEP2, BTN_WIPE

_ROOT = f"{CB_ADMIN_SECTION_PREFIX}{SECTION_PATCH}"


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_PATCH, CB_PATCH_PATCH_INFO)], [_btn(BTN_WIPE, CB_PATCH_WIPE_INFO)], [_btn(BTN_BACK, CB_ADMIN_OPEN)]]
    )


def step1_menu(wipe: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_STEP1, CB_PATCH_WIPE_STEP1 if wipe else CB_PATCH_PATCH_STEP1)], [_btn(BTN_BACK, _ROOT)]]
    )


def step2_menu(wipe: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_STEP2, CB_PATCH_WIPE_STEP2 if wipe else CB_PATCH_PATCH_STEP2)], [_btn(BTN_BACK, _ROOT)]]
    )


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, _ROOT)]])
