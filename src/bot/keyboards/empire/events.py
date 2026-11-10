"""Ивенты императора (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.empire import EMPIRE_EVENT_DURATIONS_HOURS
from bot.constant.empire import (
    CB_EMPIRE_OPEN,
    CB_EVENTS_CLAIM_PREFIX,
    CB_EVENTS_HOURS_PREFIX,
    CB_EVENTS_KIND_PREFIX,
    CB_EVENTS_OPEN,
    CB_EVENTS_START_PREFIX,
    CB_EVENTS_SUBJECT,
    EVENT_DRILL,
    EVENT_FEAST,
    EVENT_HOLIDAY,
    EVENT_KINDS,
)
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.empire import BTN_BACK_TO_EMPIRE
from bot.texts.empire.events import (
    BTN_BACK_TO_EVENTS,
    BTN_CLAIM,
    BTN_HOURS,
    BTN_OPEN_SUBJECT,
    BTN_START,
    TITLES,
)

TIMED_KINDS = (EVENT_FEAST, EVENT_HOLIDAY, EVENT_DRILL)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def events_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(TITLES[k], f"{CB_EVENTS_KIND_PREFIX}{k}") for k in EVENT_KINDS]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK_TO_EMPIRE, CB_EMPIRE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kind_menu(kind: str, *, ready: bool) -> InlineKeyboardMarkup:
    rows = []
    if ready and kind in TIMED_KINDS:
        rows.append([_btn(BTN_HOURS.format(hours=h), f"{CB_EVENTS_HOURS_PREFIX}{kind}:{h}") for h in EMPIRE_EVENT_DURATIONS_HOURS])
    rows.append([_btn(BTN_BACK_TO_EVENTS, CB_EVENTS_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_menu(kind: str, hours: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(BTN_START, f"{CB_EVENTS_START_PREFIX}{kind}:{hours}")],
        [_btn(BTN_BACK_TO_EVENTS, f"{CB_EVENTS_KIND_PREFIX}{kind}")],
    ])


def back_to_kind(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK_TO_EVENTS, f"{CB_EVENTS_KIND_PREFIX}{kind}")]])


def subject_menu(claimable: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_CLAIM.format(title=TITLES[kind]), f"{CB_EVENTS_CLAIM_PREFIX}{event_id}")] for event_id, kind in claimable]
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_menu(event_id: int | None) -> InlineKeyboardMarkup:
    """Под пушем о запуске: раздачи — сразу «Забрать», остальное — открыть ивенты."""
    if event_id is not None:
        return InlineKeyboardMarkup(inline_keyboard=[[_btn("🎁 Забрать", f"{CB_EVENTS_CLAIM_PREFIX}{event_id}")]])
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_OPEN_SUBJECT, CB_EVENTS_SUBJECT)]])
