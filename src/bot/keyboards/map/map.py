"""Карта — город игрока и его районы; для круга — карта страны и экран города (клавиатуры)."""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.game import CITY_PAGE_SIZE, DISTRICT_PAGE_SIZE
from bot.constant.common import CB_NOOP
from bot.constant.district import CB_CITY_ATTACK_BOTS_PREFIX, CB_CITY_CHALLENGE_PREFIX, CB_DISTRICT_VIEW_PREFIX
from bot.constant.map import CB_MAP_CITY_PREFIX, CB_MAP_COUNTRY_PAGE_PREFIX, CB_MAP_PAGE_PREFIX
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.map import BTN_BACK_TO_COUNTRY, BTN_MY_CITY_DISTRICTS


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def total_pages(count: int, page_size: int = DISTRICT_PAGE_SIZE) -> int:
    return max(1, (count + page_size - 1) // page_size)


def _page_rows(
    items: Sequence[tuple[str, str]], page: int, page_size: int, page_callback: str
) -> list[list[InlineKeyboardButton]]:
    """`items` — все элементы как (подпись, callback_data); страницу режет клавиатура,
    `page_callback` — префикс, к которому дописывается номер страницы."""
    pages = total_pages(len(items), page_size)
    page = max(0, min(page, pages - 1))
    start = page * page_size
    rows = [[_btn(label, data)] for label, data in items[start : start + page_size]]
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(_btn("◀️", f"{page_callback}{page - 1}"))
        nav.append(_btn(f"{page + 1}/{pages}", CB_NOOP))
        if page < pages - 1:
            nav.append(_btn("▶️", f"{page_callback}{page + 1}"))
        rows.append(nav)
    return rows


def city_map_menu(
    districts: Sequence[tuple[int, str]],
    page: int,
    *,
    back_to_country: bool = False,
    top_rows: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    """`districts` — все районы города как (district_id, подпись кнопки), по порядку
    номеров. Город — максимум 32 района, выборка из БД и так целиком одним запросом,
    пагинация здесь только про удобство экрана. У круга назад — на карту страны."""
    # События на карте (боссы, учителя) — над районами.
    rows = list(top_rows or []) + _page_rows(
        [(label, f"{CB_DISTRICT_VIEW_PREFIX}{district_id}") for district_id, label in districts],
        page,
        DISTRICT_PAGE_SIZE,
        CB_MAP_PAGE_PREFIX,
    )
    back = _btn(BTN_BACK_TO_COUNTRY, f"{CB_MAP_COUNTRY_PAGE_PREFIX}0") if back_to_country else _btn(
        BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN
    )
    rows.append([back])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def country_map_menu(
    cities: Sequence[tuple[int, str]], page: int, *, top_rows: list[list[InlineKeyboardButton]] | None = None
) -> InlineKeyboardMarkup:
    rows = list(top_rows or []) + _page_rows(
        [(label, f"{CB_MAP_CITY_PREFIX}{city_id}:0") for city_id, label in cities],
        page,
        CITY_PAGE_SIZE,
        CB_MAP_COUNTRY_PAGE_PREFIX,
    )
    rows.append([_btn(BTN_MY_CITY_DISTRICTS, f"{CB_MAP_PAGE_PREFIX}0")])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def city_owners_menu(
    city_id: int, *, bots_label: str | None, owners: Sequence[tuple[int, str]], page: int
) -> InlineKeyboardMarkup:
    """`bots_label` — кнопка боя с ботами города (None — ботов нет); `owners` — игроки,
    которым можно бросить вызов (без себя и без тех, на кого вызов уже висит)."""
    rows: list[list[InlineKeyboardButton]] = []
    if bots_label is not None:
        rows.append([_btn(bots_label, f"{CB_CITY_ATTACK_BOTS_PREFIX}{city_id}")])
    rows.extend(
        _page_rows(
            [(label, f"{CB_CITY_CHALLENGE_PREFIX}{city_id}:{owner_id}") for owner_id, label in owners],
            page,
            DISTRICT_PAGE_SIZE,
            f"{CB_MAP_CITY_PREFIX}{city_id}:",
        )
    )
    rows.append([_btn(BTN_BACK_TO_COUNTRY, f"{CB_MAP_COUNTRY_PAGE_PREFIX}0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
