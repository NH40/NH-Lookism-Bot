"""События на карте (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.event import CB_EVENT_FIGHT_PREFIX, CB_EVENT_VIEW_PREFIX, EVENT_BOSS
from bot.constant.map import CB_MAP_OPEN
from bot.services.event import EventView
from bot.texts.event import BOSS_NAMES, BTN_BACK_TO_MAP, BTN_EVENT_BOSS, BTN_EVENT_BOSS_DONE, BTN_FIGHT_BOSS
from bot.utils.formatting import format_countdown


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def event_rows(events: list[EventView], teacher_label=None) -> list[list[InlineKeyboardButton]]:
    """Кнопки событий для экрана карты (над районами/городами). `teacher_label` —
    подпись учителя (домен уникальных техник), пока учителей нет — не нужна."""
    rows = []
    for e in events:
        if e.kind == EVENT_BOSS:
            name = BOSS_NAMES.get(e.code, e.code)
            label = (
                BTN_EVENT_BOSS_DONE.format(name=name)
                if e.won
                else BTN_EVENT_BOSS.format(name=name, countdown=format_countdown(e.ends_in_seconds))
            )
        elif teacher_label is not None:
            label = teacher_label(e)
        else:
            continue
        rows.append([_btn(label, f"{CB_EVENT_VIEW_PREFIX}{e.id}")])
    return rows


def boss_menu(event_id: int, *, can_fight: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_fight:
        rows.append([_btn(BTN_FIGHT_BOSS, f"{CB_EVENT_FIGHT_PREFIX}{event_id}")])
    rows.append([_btn(BTN_BACK_TO_MAP, CB_MAP_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
