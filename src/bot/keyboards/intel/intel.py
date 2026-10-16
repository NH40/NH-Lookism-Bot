"""Разведка (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.constant.empire import CB_SABOTAGE_MARKED_PREFIX, SABOTAGE_ACTIONS
from bot.constant.intel import CB_INTEL_MARK_PREFIX, CB_INTEL_MARKS, CB_INTEL_OPEN, CB_INTEL_REPORTS
from bot.constant.position_skill import CB_SCOUT_PREFIX, CB_SCOUT_REPORT_PREFIX
from bot.texts.empire import SABOTAGE_LABELS
from bot.texts.development import BTN_BACK_TO_DEVELOPMENT
from bot.texts.intel import BTN_INTEL, BTN_MARK, BTN_MARKS, BTN_REPORTS, BTN_RESCOUT, BTN_UNMARK


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def intel_entry_rows(*, scout_or_logs: bool, marks: bool) -> list[list[InlineKeyboardButton]]:
    """Кнопки разведки для экрана «Развитие» — только если системы их открыли."""
    row = []
    if scout_or_logs or marks:
        row.append(_btn(BTN_INTEL, CB_INTEL_OPEN))
    if marks:
        row.append(_btn(BTN_MARKS, CB_INTEL_MARKS))
    return [row] if row else []


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(BTN_REPORTS, CB_INTEL_REPORTS), _btn(BTN_MARKS, CB_INTEL_MARKS)],
        [_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)],
    ])


def reports_menu(rows: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """(id цели, подпись) — по кнопке на сохранённый отчёт."""
    kb = [[_btn(label, f"{CB_SCOUT_REPORT_PREFIX}{target_id}")] for target_id, label in rows]
    kb.append([_btn(BTN_INTEL, CB_INTEL_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def report_menu(target_id: int, *, can_mark: bool, marked: bool, can_sabotage: bool = False) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_RESCOUT, f"{CB_SCOUT_PREFIX}{target_id}")]]
    if can_mark:
        rows.append([_btn(BTN_UNMARK if marked else BTN_MARK, f"{CB_INTEL_MARK_PREFIX}{target_id}")])
    if can_sabotage:
        rows.extend(
            [_btn(SABOTAGE_LABELS[action], f"{CB_SABOTAGE_MARKED_PREFIX}{action}:{target_id}")] for action in SABOTAGE_ACTIONS
        )
    rows.append([_btn(BTN_INTEL, CB_INTEL_OPEN), _btn(BTN_REPORTS, CB_INTEL_REPORTS)])
    rows.append([_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
