"""Банда игрока — экран банды, распределение статистов по лагерям (клавиатуры)."""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.game import GANG_CAMP_MOVE_PERCENTS, GANG_SQUAD_MOVE_AMOUNTS, GANG_SQUADS_PAGE_SIZE
from bot.constant.collection import CB_COLLECTION_OPEN
from bot.constant.common import CB_MENU_SETTINGS, CB_NOOP
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.constant.gang import (
    AMOUNT_ALL,
    AMOUNT_HALF,
    CB_GANG_BACK,
    CB_GANG_CAMP_MOVE_PREFIX,
    CB_GANG_DELETE_CONFIRM,
    CB_GANG_LINEUP,
    CB_GANG_POSITION_CLEAR_PREFIX,
    CB_GANG_POSITION_PREFIX,
    CB_GANG_POSITION_SET_PREFIX,
    CB_GANG_SQUAD_CUSTOM_PREFIX,
    CB_GANG_SQUAD_MOVE_PREFIX,
    CB_GANG_SQUAD_PREFIX,
    CB_GANG_SQUADS_PREFIX,
)
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.settings import BTN_BACK_TO_SETTINGS
from bot.texts.gang import (
    AMOUNT_HALF_LABEL,
    BTN_BACK_TO_GANG,
    BTN_BACK_TO_LINEUP,
    BTN_COLLECTION,
    BTN_DELETE_CONFIRM,
    BTN_LINEUP,
    BTN_BACK_TO_SQUAD,
    BTN_BACK_TO_SQUADS,
    BTN_SQUAD_CUSTOM_TO_ATTACK,
    BTN_SQUAD_CUSTOM_TO_DEFENSE,
    BTN_SQUADS,
    BTN_TO_ATTACK,
    BTN_TO_DEFENSE,
    PERCENT_ALL_LABEL,
)


def _percent_label(percent: int) -> str:
    return PERCENT_ALL_LABEL if percent == 100 else f"{percent}%"


def _move_row(template: str, from_camp: str, to_camp: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text=template.format(label=_percent_label(p)),
            callback_data=f"{CB_GANG_CAMP_MOVE_PREFIX}{from_camp}:{to_camp}:{p}",
        )
        for p in GANG_CAMP_MOVE_PERCENTS
    ]


def gang_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _move_row(BTN_TO_DEFENSE, CAMP_ATTACK, CAMP_DEFENSE),
            _move_row(BTN_TO_ATTACK, CAMP_DEFENSE, CAMP_ATTACK),
            [InlineKeyboardButton(text=BTN_SQUADS, callback_data=f"{CB_GANG_SQUADS_PREFIX}0")],
            [
                InlineKeyboardButton(text=BTN_COLLECTION, callback_data=CB_COLLECTION_OPEN),
                InlineKeyboardButton(text=BTN_LINEUP, callback_data=CB_GANG_LINEUP),
            ],
            [InlineKeyboardButton(text=BTN_BACK_TO_PROFILE, callback_data=CB_PROFILE_OPEN)],
        ]
    )


def lineup_menu(slots: Sequence[tuple[str, str]]) -> InlineKeyboardMarkup:
    """`slots` — все 9 позиций как (позиция, подпись «👑 Глава: 🟧 Elite (Prime)»)."""
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{CB_GANG_POSITION_PREFIX}{position}:0")]
        for position, label in slots
    ]
    rows.append(
        [
            InlineKeyboardButton(text=BTN_COLLECTION, callback_data=CB_COLLECTION_OPEN),
            InlineKeyboardButton(text=BTN_BACK_TO_GANG, callback_data=CB_GANG_BACK),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def position_menu(
    position: str, *, choices: Sequence[tuple[str, str]], page: int, clear_label: str | None
) -> InlineKeyboardMarkup:
    """`choices` — подходящие карты со свободной копией как (код, подпись); страницу режет
    клавиатура. `clear_label` — кнопка «снять», если позиция занята."""
    size = GANG_SQUADS_PAGE_SIZE
    pages = max(1, (len(choices) + size - 1) // size)
    page = max(0, min(page, pages - 1))
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{CB_GANG_POSITION_SET_PREFIX}{position}:{code}")]
        for code, label in choices[page * size : (page + 1) * size]
    ]
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{CB_GANG_POSITION_PREFIX}{position}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=CB_NOOP))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{CB_GANG_POSITION_PREFIX}{position}:{page + 1}"))
        rows.append(nav)
    if clear_label is not None:
        rows.append([InlineKeyboardButton(text=clear_label, callback_data=f"{CB_GANG_POSITION_CLEAR_PREFIX}{position}")])
    rows.append([InlineKeyboardButton(text=BTN_BACK_TO_LINEUP, callback_data=CB_GANG_LINEUP)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def squads_total_pages(count: int) -> int:
    return max(1, (count + GANG_SQUADS_PAGE_SIZE - 1) // GANG_SQUADS_PAGE_SIZE)


def squad_key(rank: str, stars: int, training_level: int, school: str = "", school_level: int = 0) -> str:
    return f"{rank}:{stars}:{training_level}:{school}:{school_level}"


def squads_menu(squads: Sequence[tuple[str, str]], page: int) -> InlineKeyboardMarkup:
    """`squads` — все отряды как (ключ `squad_key`, подпись кнопки), уже в порядке показа;
    клавиатура сама режет страницу (тот же приём, что у карты города). Отрядов на игрока
    мало (ранг×звёзды×уровень), выборка и так целиком одним запросом."""
    pages = squads_total_pages(len(squads))
    page = max(0, min(page, pages - 1))
    start = page * GANG_SQUADS_PAGE_SIZE

    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{CB_GANG_SQUAD_PREFIX}{key}")]
        for key, label in squads[start : start + GANG_SQUADS_PAGE_SIZE]
    ]
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{CB_GANG_SQUADS_PREFIX}{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=CB_NOOP))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{CB_GANG_SQUADS_PREFIX}{page + 1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=BTN_BACK_TO_GANG, callback_data=CB_GANG_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _squad_move_rows(
    key: str, template: str, custom_label: str, from_camp: str
) -> list[list[InlineKeyboardButton]]:
    prefix = f"{CB_GANG_SQUAD_MOVE_PREFIX}{key}:{from_camp}:"
    exact = [
        InlineKeyboardButton(text=template.format(label=n), callback_data=f"{prefix}{n}")
        for n in GANG_SQUAD_MOVE_AMOUNTS
    ]
    shares = [
        InlineKeyboardButton(text=template.format(label=AMOUNT_HALF_LABEL), callback_data=f"{prefix}{AMOUNT_HALF}"),
        InlineKeyboardButton(text=template.format(label=PERCENT_ALL_LABEL), callback_data=f"{prefix}{AMOUNT_ALL}"),
        InlineKeyboardButton(text=custom_label, callback_data=f"{CB_GANG_SQUAD_CUSTOM_PREFIX}{key}:{from_camp}"),
    ]
    return [exact, shares]


def squad_menu(rank: str, stars: int, training_level: int, school: str = "", school_level: int = 0) -> InlineKeyboardMarkup:
    key = squad_key(rank, stars, training_level, school, school_level)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *_squad_move_rows(key, BTN_TO_DEFENSE, BTN_SQUAD_CUSTOM_TO_DEFENSE, CAMP_ATTACK),
            *_squad_move_rows(key, BTN_TO_ATTACK, BTN_SQUAD_CUSTOM_TO_ATTACK, CAMP_DEFENSE),
            [InlineKeyboardButton(text=BTN_BACK_TO_SQUADS, callback_data=f"{CB_GANG_SQUADS_PREFIX}0")],
        ]
    )


def squad_back_menu(rank: str, stars: int, training_level: int, school: str = "", school_level: int = 0) -> InlineKeyboardMarkup:
    """Кнопка «назад» под промптом своего числа — возвращает на экран отряда (тот же
    callback, что и кнопка отряда в списке; его хендлер сам чистит FSM-состояние)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_BACK_TO_SQUAD,
                    callback_data=f"{CB_GANG_SQUAD_PREFIX}{squad_key(rank, stars, training_level, school, school_level)}",
                )
            ]
        ]
    )


def delete_confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_DELETE_CONFIRM, callback_data=CB_GANG_DELETE_CONFIRM)],
            [InlineKeyboardButton(text=BTN_BACK_TO_SETTINGS, callback_data=CB_MENU_SETTINGS)],
        ]
    )
