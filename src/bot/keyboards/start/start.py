"""/start — вход в игру (клавиатуры).

Онбординг страны/города — см. `services/start`. Остальные экраны /start (заглушка
приветствия для полностью прошедших онбординг игроков) — TODO, ждут `profile`/`map`.
"""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config.country import COUNTRIES
from bot.config.game import CITY_PAGE_SIZE
from bot.constant.common import CB_NOOP
from bot.constant.start import (
    CB_START_BACK_TO_COUNTRY,
    CB_START_CITY_PAGE_PREFIX,
    CB_START_CITY_PREFIX,
    CB_START_COUNTRY_PREFIX,
)
from bot.db.models.city import City


def country_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for country in COUNTRIES:
        builder.button(text=country.name, callback_data=f"{CB_START_COUNTRY_PREFIX}{country.code}")
    builder.adjust(2)
    return builder.as_markup()


def city_menu(country_code: str, cities: Sequence[City], page: int) -> InlineKeyboardMarkup:
    """`page` — 0-based. `cities` — уже отсортированный полный список городов страны
    (репозиторий сортирует по размеру, см. `db/repositories/city.list_by_country`) —
    список коротких (<200 городов даже для России), пагинация тут — чисто про удобство
    экрана, не про объём запроса к БД (правило 7 всё равно соблюдено: сам список городов
    статичен и укладывается в один запрос целиком)."""
    total_pages = max(1, (len(cities) + CITY_PAGE_SIZE - 1) // CITY_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * CITY_PAGE_SIZE
    page_cities = cities[start : start + CITY_PAGE_SIZE]

    builder = InlineKeyboardBuilder()
    for city in page_cities:
        builder.button(
            text=f"{city.name} ({city.district_count} р.)",
            callback_data=f"{CB_START_CITY_PREFIX}{city.id}",
        )
    builder.adjust(1)

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️", callback_data=f"{CB_START_CITY_PAGE_PREFIX}{country_code}:{page - 1}"
            )
        )
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=CB_NOOP))
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="▶️", callback_data=f"{CB_START_CITY_PAGE_PREFIX}{country_code}:{page + 1}"
            )
        )
    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="◀️ Другая страна", callback_data=CB_START_BACK_TO_COUNTRY))
    return builder.as_markup()
