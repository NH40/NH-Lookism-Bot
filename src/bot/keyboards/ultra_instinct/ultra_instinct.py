"""Ультра инстинкт — экран настроек (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.bloodline import CB_BLOODLINE_SCREEN
from bot.constant.event import BOSSES
from bot.constant.ultra_instinct import (
    ACTIONS,
    CB_ULTRA_ACTION_PREFIX,
    CB_ULTRA_BOSS_PREFIX,
    CB_ULTRA_LOSS_PREFIX,
)
from bot.services.ultra_instinct.ultra_instinct import ULTRA_LOSS_OPTIONS, UltraView
from bot.texts.bloodline import BTN_BACK_TO_BLOODLINE
from bot.texts.event import BOSS_NAMES
from bot.texts.ultra_instinct import ACTION_LABELS, BTN_ACTION, BTN_BOSS, BTN_LOSS, MARK_OFF, MARK_ON


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def ultra_menu(view: UltraView) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_ACTION.format(mark=MARK_ON if view.enabled[a] else MARK_OFF, label=ACTION_LABELS[a]), f"{CB_ULTRA_ACTION_PREFIX}{a}")]
        for a in ACTIONS
        if view.available[a]
    ]
    if view.boss_available:
        rows.extend(
            [_btn(BTN_BOSS.format(mark=MARK_ON if code in view.bosses else MARK_OFF, name=BOSS_NAMES[code]), f"{CB_ULTRA_BOSS_PREFIX}{code}")]
            for code in BOSSES
        )
        rows.append([
            _btn(BTN_LOSS.format(mark="· " if percent == view.max_loss else "", percent=percent), f"{CB_ULTRA_LOSS_PREFIX}{percent}")
            for percent in ULTRA_LOSS_OPTIONS
        ])
    rows.append([_btn(BTN_BACK_TO_BLOODLINE, CB_BLOODLINE_SCREEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
