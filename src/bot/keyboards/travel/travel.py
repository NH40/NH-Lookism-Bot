"""Переезд (клавиатуры)."""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.country import COUNTRIES
from bot.config.game import CITY_PAGE_SIZE
from bot.constant.common import CB_NOOP
from bot.constant.map import CB_MAP_OPEN
from bot.constant.travel import (
    CB_TRAVEL_ABANDON,
    CB_TRAVEL_ABANDON_ASK,
    CB_TRAVEL_CITIES_PREFIX,
    CB_TRAVEL_COUNTRIES,
    CB_TRAVEL_GO_PREFIX,
    CB_TRAVEL_OPEN,
    CB_TRAVEL_PICK_PREFIX,
)
from bot.db.models.city import City
from bot.texts.travel import (
    BTN_BACK_TO_TRAVEL,
    BTN_OTHER_COUNTRY,
    BTN_TO_MAP,
    BTN_TRAVEL_ABANDON,
    BTN_TRAVEL_ABANDON_YES,
    BTN_TRAVEL_CITY,
    BTN_TRAVEL_COUNTRY,
    BTN_TRAVEL_GO,
)


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def travel_menu(country_code: str, *, must_abandon: bool, can_leave_country: bool) -> InlineKeyboardMarkup:
    if must_abandon:
        rows = [[_btn(BTN_TRAVEL_ABANDON, CB_TRAVEL_ABANDON_ASK)]]
    else:
        rows = [[_btn(BTN_TRAVEL_CITY, f"{CB_TRAVEL_CITIES_PREFIX}{country_code}:0")]]
        if can_leave_country:
            rows.append([_btn(BTN_TRAVEL_COUNTRY, CB_TRAVEL_COUNTRIES)])
    rows.append([_btn(BTN_TO_MAP, CB_MAP_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def countries_menu(exclude: set[str]) -> InlineKeyboardMarkup:
    buttons = [_btn(c.name, f"{CB_TRAVEL_CITIES_PREFIX}{c.code}:0") for c in COUNTRIES if c.code not in exclude]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK_TO_TRAVEL, CB_TRAVEL_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cities_menu(country_code: str, cities: Sequence[City], page: int, *, own_country: bool) -> InlineKeyboardMarkup:
    pages = max(1, (len(cities) + CITY_PAGE_SIZE - 1) // CITY_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = [
        [_btn(f"{c.name} ({c.district_count} р.)", f"{CB_TRAVEL_PICK_PREFIX}{c.id}")]
        for c in cities[page * CITY_PAGE_SIZE : (page + 1) * CITY_PAGE_SIZE]
    ]
    nav = []
    if page > 0:
        nav.append(_btn("◀️", f"{CB_TRAVEL_CITIES_PREFIX}{country_code}:{page - 1}"))
    if pages > 1:
        nav.append(_btn(f"{page + 1}/{pages}", CB_NOOP))
    if page < pages - 1:
        nav.append(_btn("▶️", f"{CB_TRAVEL_CITIES_PREFIX}{country_code}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(BTN_BACK_TO_TRAVEL, CB_TRAVEL_OPEN) if own_country else _btn(BTN_OTHER_COUNTRY, CB_TRAVEL_COUNTRIES)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_menu(city_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_TRAVEL_GO, f"{CB_TRAVEL_GO_PREFIX}{city_id}")], [_btn(BTN_BACK_TO_TRAVEL, CB_TRAVEL_OPEN)]]
    )


def abandon_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_TRAVEL_ABANDON_YES, CB_TRAVEL_ABANDON)], [_btn(BTN_BACK_TO_TRAVEL, CB_TRAVEL_OPEN)]]
    )


def after_move_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_TO_MAP, CB_MAP_OPEN)], [_btn(BTN_BACK_TO_TRAVEL, CB_TRAVEL_OPEN)]])
