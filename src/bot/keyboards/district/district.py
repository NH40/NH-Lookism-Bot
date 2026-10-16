"""Районы — карточка района, отчёт о бое, вызов (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.position_skill import CB_SCOUT_PREFIX
from bot.texts.intel import BTN_SCOUT
from bot.config.game import DISTRICT_PAGE_SIZE
from bot.constant.business import CB_BUSINESS_DISTRICT_PREFIX
from bot.constant.district import CB_CHALLENGE_ACCEPT_PREFIX, CB_CITY_ATTACK_BOTS_PREFIX, CB_DISTRICT_ATTACK_PREFIX
from bot.constant.map import CB_MAP_CITY_PREFIX, CB_MAP_PAGE_PREFIX
from bot.texts.business import BTN_DISTRICT_BUSINESSES
from bot.texts.district import BTN_ACCEPT, BTN_ATTACK_AGAIN, BTN_ATTACK_CITY_AGAIN, BTN_BACK_TO_CITY, BTN_BACK_TO_MAP


def _back_to_map(number: int) -> InlineKeyboardButton:
    """Назад на ту страницу карты, где этот район и был — страница вычисляется из номера
    района, не таскается отдельно в callback_data."""
    page = (number - 1) // DISTRICT_PAGE_SIZE
    return InlineKeyboardButton(text=BTN_BACK_TO_MAP, callback_data=f"{CB_MAP_PAGE_PREFIX}{page}")


def district_menu(
    district_id: int, number: int, *, action_label: str | None, is_mine: bool = False, scout_target: int | None = None
) -> InlineKeyboardMarkup:
    """`action_label` — `BTN_ATTACK` (район у ботов), `BTN_CHALLENGE` (район игрока) или
    `None` (свой район / на район уже висит вызов). Обе кнопки ведут в один и тот же
    callback — бот это район или игрок, решает сервис, не клавиатура. Свой район —
    кнопка в его бизнесы (домен `business`)."""
    rows = []
    if is_mine:
        rows.append(
            [InlineKeyboardButton(text=BTN_DISTRICT_BUSINESSES, callback_data=f"{CB_BUSINESS_DISTRICT_PREFIX}{district_id}")]
        )
    if action_label is not None:
        rows.append([InlineKeyboardButton(text=action_label, callback_data=f"{CB_DISTRICT_ATTACK_PREFIX}{district_id}")])
    if scout_target is not None:  # район держит игрок — разведать его (отдельный этап, без КД)
        rows.append([InlineKeyboardButton(text=BTN_SCOUT, callback_data=f"{CB_SCOUT_PREFIX}{scout_target}")])
    rows.append([_back_to_map(number)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_menu(district_id: int, number: int, *, can_attack_again: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_attack_again:
        rows.append(
            [InlineKeyboardButton(text=BTN_ATTACK_AGAIN, callback_data=f"{CB_DISTRICT_ATTACK_PREFIX}{district_id}")]
        )
    rows.append([_back_to_map(number)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def accept_menu(challenge_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BTN_ACCEPT, callback_data=f"{CB_CHALLENGE_ACCEPT_PREFIX}{challenge_id}")]]
    )


def city_report_menu(city_id: int, *, can_attack_again: bool) -> InlineKeyboardMarkup:
    """Отчёт о бое круга с ботами города: проиграл — можно снова (после КД), и назад в город."""
    rows = []
    if can_attack_again:
        rows.append(
            [InlineKeyboardButton(text=BTN_ATTACK_CITY_AGAIN, callback_data=f"{CB_CITY_ATTACK_BOTS_PREFIX}{city_id}")]
        )
    rows.append([InlineKeyboardButton(text=BTN_BACK_TO_CITY, callback_data=f"{CB_MAP_CITY_PREFIX}{city_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
