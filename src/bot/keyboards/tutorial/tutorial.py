"""Лига-обучение (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.tutorial import (
    STEP_BLOODLINE,
    STEP_DEVELOP,
    STEP_GENIUS,
    STEP_MASTERY,
    STEP_RECRUIT,
    STEP_TECHNIQUE,
    TRAINING_LESSONS,
)
from bot.constant.bloodline import CB_BLOODLINE_LIST
from bot.constant.characteristic import CB_STATS_OPEN
from bot.constant.genius import CB_GENIUS_OPEN
from bot.constant.mastery import CB_MASTERY_OPEN
from bot.constant.profile import CB_PROFILE_OPEN
from bot.constant.recruit import CB_RECRUIT_OPEN
from bot.constant.tutorial import CB_TUT_ATTACK_PREFIX, CB_TUT_BUILD_PREFIX, CB_TUT_CHECK, CB_TUT_COLLECT, CB_TUT_OPEN, CB_TUT_START
from bot.constant.unique_technique import CB_TECH_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.tutorial import (
    BTN_ATTACK,
    BTN_ATTACK_CITY,
    BTN_BUILD,
    BTN_CHECK,
    BTN_COLLECT,
    BTN_GOT_IT,
    BTN_GOTO,
    BTN_REFRESH,
    BTN_START,
)

_GOTO = {
    STEP_RECRUIT: CB_RECRUIT_OPEN, STEP_DEVELOP: CB_STATS_OPEN, STEP_BLOODLINE: CB_BLOODLINE_LIST,
    STEP_GENIUS: CB_GENIUS_OPEN, STEP_TECHNIQUE: CB_TECH_OPEN, STEP_MASTERY: CB_MASTERY_OPEN,
}


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def tutorial_menu(view) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for city in view.cities:
        if not city.open or all(city.owned):
            continue
        if city.whole:
            rows.append([_b(BTN_ATTACK_CITY.format(name=city.name), f"{CB_TUT_ATTACK_PREFIX}{city.index}:-1")])
        else:
            free = [i for i, o in enumerate(city.owned) if not o]
            rows.append([_b(BTN_ATTACK.format(name="Посёлок", n=i + 1), f"{CB_TUT_ATTACK_PREFIX}{city.index}:{i}") for i in free[:2]])
    spot = next(((c.index, i) for c in view.cities for i, o in enumerate(c.owned) if o and c.buildings[i] < view.capacity), None)
    actions = []
    if spot is not None:
        actions.append(_b(BTN_BUILD.format(n=spot[1] + 1), f"{CB_TUT_BUILD_PREFIX}{spot[0]}:{spot[1]}"))
    if any(sum(c.buildings) for c in view.cities):
        actions.append(_b(BTN_COLLECT, CB_TUT_COLLECT))
    if actions:
        rows.append(actions)
    if view.code in _GOTO:
        rows.append([_b(BTN_GOTO, _GOTO[view.code])])
    rows.append([_b(BTN_GOT_IT if view.code in TRAINING_LESSONS else BTN_CHECK, CB_TUT_CHECK), _b(BTN_REFRESH, CB_TUT_OPEN)])
    rows.append([_b(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_START, CB_TUT_START)], [_b(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)]])


def open_menu() -> InlineKeyboardMarkup:
    from bot.texts.tutorial import BTN_OPEN

    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_OPEN, CB_TUT_OPEN)]])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)]])
