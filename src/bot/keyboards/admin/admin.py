"""Админ-панель и бета-режим (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import (
    CB_ADMIN_FIND,
    CB_ADMIN_PLAYER_DEV_PREFIX,
    CB_ADMIN_PLAYER_GIVE_PREFIX,
    CB_ADMIN_PLAYER_LOG_PREFIX,
    CB_ADMIN_PLAYER_PREFIX,
    CB_ADMIN_PLAYER_PUNISH_PREFIX,
    CB_ADMIN_SECTION_PREFIX,
    SECTION_SYSTEM,
    CB_ADMIN_BETA_CODE,
    CB_ADMIN_BETA_GENERATE,
    CB_ADMIN_BETA_OFF,
    CB_ADMIN_BETA_OFF_ASK,
    CB_ADMIN_BETA_ON,
    CB_ADMIN_OPEN,
    CB_ADMIN_TECH_TOGGLE,
)
from bot.texts.admin import (
    BTN_BACK_TO_PLAYER,
    BTN_FIND_ANOTHER,
    BTN_PLAYER_DEV,
    BTN_PLAYER_GIVE,
    BTN_PLAYER_LOG,
    BTN_PLAYER_PUNISH,
    BTN_REFRESH,
    SECTION_TITLES,
    BTN_BACK,
    BTN_BETA_CODE,
    BTN_BETA_OFF,
    BTN_BETA_ON,
    BTN_CONFIRM_OFF,
    BTN_GENERATE,
    BTN_TECH_OFF,
    BTN_TECH_ON,
)


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def panel_menu(*, beta_on: bool, tech_on: bool) -> InlineKeyboardMarkup:
    rows = (
        [[_btn(BTN_BETA_CODE, CB_ADMIN_BETA_CODE)], [_btn(BTN_BETA_OFF, CB_ADMIN_BETA_OFF_ASK)]]
        if beta_on
        else [[_btn(BTN_BETA_ON, CB_ADMIN_BETA_ON)]]
    )
    rows.append([_btn(BTN_TECH_OFF if tech_on else BTN_TECH_ON, CB_ADMIN_TECH_TOGGLE)])
    rows.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu(sections: list[str]) -> InlineKeyboardMarkup:
    """Главное меню админки: кнопки разделов, доступных роли, по две в ряд."""
    buttons = [_btn(SECTION_TITLES[s], f"{CB_ADMIN_SECTION_PREFIX}{s}") for s in sections]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def back_to_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, CB_ADMIN_OPEN)]])


def back_to_player(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK_TO_PLAYER, f"{CB_ADMIN_PLAYER_PREFIX}{user_id}")]])


def player_menu(user_id: int, *, give: bool, dev: bool, punish: bool, logs: bool, phase: str | None = None) -> InlineKeyboardMarkup:
    """Карточка игрока: действия — по правам роли."""
    rows = []
    actions = []
    if give:
        actions.append(_btn(BTN_PLAYER_GIVE, f"{CB_ADMIN_PLAYER_GIVE_PREFIX}{user_id}"))
    if dev:
        actions.append(_btn(BTN_PLAYER_DEV, f"{CB_ADMIN_PLAYER_DEV_PREFIX}{user_id}"))
    if actions:
        rows.append(actions)
    if dev:
        from bot.constant.admin import CB_ADMIN_PLAYER_QUESTS_PREFIX
        from bot.texts.admin import BTN_PLAYER_QUESTS

        rows.append([_btn(BTN_PLAYER_QUESTS, f"{CB_ADMIN_PLAYER_QUESTS_PREFIX}{user_id}")])
        # Фаза — быстрый перевод по стадиям (2026-10-13), текущая отмечена.
        from bot.constant.admin.players_admin import CB_ADMIN_PHASE
        from bot.constant.phase import PHASE_ORDER as PHASES
        from bot.texts.profile import PHASE_LABELS

        rows.append([
            _btn(f"{'• ' if p == phase else ''}{PHASE_LABELS.get(p, p)}", f"{CB_ADMIN_PHASE}{p}:{user_id}") for p in PHASES
        ])
    actions = []
    if punish:
        actions.append(_btn(BTN_PLAYER_PUNISH, f"{CB_ADMIN_PLAYER_PUNISH_PREFIX}{user_id}"))
    if logs:
        actions.append(_btn(BTN_PLAYER_LOG, f"{CB_ADMIN_PLAYER_LOG_PREFIX}{user_id}"))
    if actions:
        rows.append(actions)
    rows.append([_btn(BTN_REFRESH, f"{CB_ADMIN_PLAYER_PREFIX}{user_id}"), _btn(BTN_FIND_ANOTHER, CB_ADMIN_FIND)])
    rows.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def code_prompt_menu() -> InlineKeyboardMarkup:
    """Под промптом кода: сгенерировать или назад (хендлер назад чистит FSM)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_GENERATE, CB_ADMIN_BETA_GENERATE)], [_btn(BTN_BACK, f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SYSTEM}")]]
    )


def off_confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_CONFIRM_OFF, CB_ADMIN_BETA_OFF)], [_btn(BTN_BACK, f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SYSTEM}")]]
    )


def player_quests_menu(user_id: int, daily: list[tuple[int, str]], dev: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Задания игрока: кнопка на каждое невыполненное (засчитать) и «Засчитать все»."""
    from bot.constant.admin import CB_ADMIN_QUEST_ALL_PREFIX, CB_ADMIN_QUEST_DAILY_PREFIX, CB_ADMIN_QUEST_DEV_PREFIX
    from bot.texts.admin import BTN_QUEST_ALL, BTN_QUEST_DAILY, BTN_QUEST_DEV

    rows = [[_btn(BTN_QUEST_DAILY.format(label=label), f"{CB_ADMIN_QUEST_DAILY_PREFIX}{slot}:{user_id}")] for slot, label in daily]
    rows += [[_btn(BTN_QUEST_DEV.format(title=title), f"{CB_ADMIN_QUEST_DEV_PREFIX}{qid}:{user_id}")] for qid, title in dev]
    if daily or dev:
        rows.append([_btn(BTN_QUEST_ALL, f"{CB_ADMIN_QUEST_ALL_PREFIX}{user_id}")])
    rows.append([_btn(BTN_BACK, f"{CB_ADMIN_PLAYER_PREFIX}{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
