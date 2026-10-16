"""Император — экран «👑 Империя», налоги (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.empire import EMPIRE_TAX_STEPS
from bot.constant.empire import (
    CB_EMPIRE_OPEN,
    CB_EMPIRE_PERSONAL,
    CB_EMPIRE_PERSONAL_RATE_PREFIX,
    CB_EMPIRE_RATE_PREFIX,
    CB_SABOTAGE_DO_PREFIX,
    CB_WAR_ACCEPT_PREFIX,
    CB_WAR_DECLARE_PREFIX,
    CB_WAR_LIST_PREFIX,
    CB_WAR_TARGET_PREFIX,
    EMPIRE_RATE_RESET,
    SABOTAGE_ACTIONS,
)
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.empire import (
    BTN_BACK_TO_EMPIRE,
    BTN_BACK_TO_TARGETS,
    BTN_NEXT,
    BTN_PERSONAL,
    BTN_PREV,
    BTN_RATE,
    BTN_RATE_CURRENT,
    BTN_RESET_PERSONAL,
    BTN_SABOTAGE_ACTION,
    BTN_SABOTAGE_COOLDOWN,
    BTN_WAR,
    BTN_WAR_ACCEPT,
    BTN_WAR_DECLARE,
    SABOTAGE_CHANCES,
    SABOTAGE_LABELS,
)


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _rate_row(current: int, prefix: str) -> list[InlineKeyboardButton]:
    return [
        _btn((BTN_RATE_CURRENT if p == current else BTN_RATE).format(percent=p), f"{prefix}{p}")
        for p in EMPIRE_TAX_STEPS
    ]


def empire_menu(current_rate: int, incoming_war_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        _rate_row(current_rate, CB_EMPIRE_RATE_PREFIX),
        [_btn(BTN_PERSONAL, CB_EMPIRE_PERSONAL)],
    ]
    if incoming_war_id is not None:
        rows.append([_btn(BTN_WAR_ACCEPT, f"{CB_WAR_ACCEPT_PREFIX}{incoming_war_id}")])
    rows.append([_btn(BTN_WAR, f"{CB_WAR_LIST_PREFIX}0")])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def personal_rate_menu(subject_id: int, current: int, *, has_override: bool) -> InlineKeyboardMarkup:
    rows = [_rate_row(current if has_override else -1, f"{CB_EMPIRE_PERSONAL_RATE_PREFIX}{subject_id}:")]
    if has_override:
        rows.append([_btn(BTN_RESET_PERSONAL, f"{CB_EMPIRE_PERSONAL_RATE_PREFIX}{subject_id}:{EMPIRE_RATE_RESET}")])
    rows.append([_btn(BTN_BACK_TO_EMPIRE, CB_EMPIRE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_empire_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK_TO_EMPIRE, CB_EMPIRE_OPEN)]])


def sabotage_menu(cooldowns: dict[str, str | None]) -> InlineKeyboardMarkup:
    """`cooldowns` — действие → отсчёт до попытки (None — готово). Кнопка на перерыве тоже
    кликабельна: Telegram не умеет выключать кнопки, клик отвечает алертом с таймером."""
    rows = [
        [
            _btn(
                BTN_SABOTAGE_COOLDOWN.format(label=SABOTAGE_LABELS[action], countdown=cooldowns[action])
                if cooldowns.get(action)
                else BTN_SABOTAGE_ACTION.format(label=SABOTAGE_LABELS[action], chance=SABOTAGE_CHANCES[action]),
                f"{CB_SABOTAGE_DO_PREFIX}{action}",
            )
        ]
        for action in SABOTAGE_ACTIONS
    ]
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def war_targets_menu(targets: list[tuple[int, str]], page: int, has_more: bool) -> InlineKeyboardMarkup:
    """`targets` — (user_id, подпись кнопки)."""
    rows = [[_btn(label, f"{CB_WAR_TARGET_PREFIX}{uid}")] for uid, label in targets]
    nav = []
    if page > 0:
        nav.append(_btn(BTN_PREV, f"{CB_WAR_LIST_PREFIX}{page - 1}"))
    if has_more:
        nav.append(_btn(BTN_NEXT, f"{CB_WAR_LIST_PREFIX}{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(BTN_BACK_TO_EMPIRE, CB_EMPIRE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def war_target_menu(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_WAR_DECLARE, f"{CB_WAR_DECLARE_PREFIX}{target_id}")],
            [_btn(BTN_BACK_TO_TARGETS, f"{CB_WAR_LIST_PREFIX}0")],
        ]
    )


def war_accept_menu(war_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_WAR_ACCEPT, f"{CB_WAR_ACCEPT_PREFIX}{war_id}")]])
