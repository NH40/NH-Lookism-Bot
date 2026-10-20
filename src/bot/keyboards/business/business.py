"""Бизнесы на районе — кофе/зал/магазин/нелегальный рынок/парламент, прокачка уровень/вместимость (клавиатуры)."""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.game import BUSINESS_BUILD_COST, DISTRICT_PAGE_SIZE
from bot.constant.business import (
    BUSINESS_TYPES,
    CB_BUSINESS_BUILD_PREFIX,
    CB_BUSINESS_COLLECT,
    CB_BUSINESS_DEMOLISH_ALL_ASK_PREFIX,
    CB_BUSINESS_DEMOLISH_ALL_PREFIX,
    CB_BUSINESS_DEMOLISH_EVERY_ALL,
    CB_BUSINESS_DEMOLISH_EVERY_ALL_ASK,
    CB_BUSINESS_DEMOLISH_EVERY_MENU,
    CB_BUSINESS_DEMOLISH_EVERY_PREFIX,
    CB_BUSINESS_DEMOLISH_MENU_PREFIX,
    CB_BUSINESS_DEMOLISH_PREFIX,
    CB_BUSINESS_FILL_MENU_PREFIX,
    CB_BUSINESS_FILL_PREFIX,
    CB_BUSINESS_DISTRICT_PREFIX,
    CB_BUSINESS_PAGE_PREFIX,
    CB_BUSINESS_UPGRADE_PREFIX,
    CB_BUSINESS_OPEN,
    UPGRADE_CAPACITY,
    UPGRADE_LEVEL,
)
from bot.constant.common import CB_NOOP
from bot.constant.district import CB_DISTRICT_VIEW_PREFIX
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.business import (
    BTN_BACK_TO_BUSINESS,
    BTN_BUILD,
    BTN_CANCEL,
    BTN_COLLECT,
    BTN_DEMOLISH,
    BTN_DEMOLISH_ALL,
    BTN_DEMOLISH_ALL_CONFIRM,
    BTN_DEMOLISH_EVERY_ALL,
    BTN_DEMOLISH_EVERY_TYPE,
    BTN_DEMOLISH_EVERYWHERE,
    BTN_DEMOLISH_ONE,
    BTN_FILL,
    BTN_FILL_ALL_DISTRICTS,
    BTN_FILL_TYPE,
    BTN_TO_DISTRICT,
    BTN_UPGRADE_CAPACITY,
    BTN_UPGRADE_CAPACITY_MAX,
    BTN_UPGRADE_LEVEL,
    BTN_UPGRADE_LEVEL_MAX,
    BUSINESS_NAMES,
)
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _upgrade_button(kind: str, current: int, cost: int | None) -> InlineKeyboardButton:
    if cost is None:
        label = BTN_UPGRADE_LEVEL_MAX if kind == UPGRADE_LEVEL else BTN_UPGRADE_CAPACITY_MAX
        return _btn(label, CB_NOOP)
    template = BTN_UPGRADE_LEVEL if kind == UPGRADE_LEVEL else BTN_UPGRADE_CAPACITY
    return _btn(template.format(next=current + 1, cost=format_number(cost)), f"{CB_BUSINESS_UPGRADE_PREFIX}{kind}")


def overview_menu(
    *,
    pending: int,
    districts: Sequence[tuple[int, str]],
    page: int,
    level: int,
    level_cost: int | None,
    capacity: int,
    capacity_cost: int | None,
) -> InlineKeyboardMarkup:
    """`districts` — все районы игрока как (district_id, подпись); страницу режет клавиатура
    (районов у банды — не больше, чем в её городе, выборка и так одним запросом)."""
    rows: list[list[InlineKeyboardButton]] = []
    if pending > 0:
        rows.append([_btn(BTN_COLLECT.format(amount=format_number(pending)), CB_BUSINESS_COLLECT)])

    pages = max(1, (len(districts) + DISTRICT_PAGE_SIZE - 1) // DISTRICT_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * DISTRICT_PAGE_SIZE
    rows.extend(
        [_btn(label, f"{CB_BUSINESS_DISTRICT_PREFIX}{district_id}")]
        for district_id, label in districts[start : start + DISTRICT_PAGE_SIZE]
    )
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(_btn("◀️", f"{CB_BUSINESS_PAGE_PREFIX}{page - 1}"))
        nav.append(_btn(f"{page + 1}/{pages}", CB_NOOP))
        if page < pages - 1:
            nav.append(_btn("▶️", f"{CB_BUSINESS_PAGE_PREFIX}{page + 1}"))
        rows.append(nav)
    if districts:
        rows.append([_btn(BTN_FILL_ALL_DISTRICTS, f"{CB_BUSINESS_FILL_MENU_PREFIX}0")])
        rows.append([_btn(BTN_DEMOLISH_EVERYWHERE, CB_BUSINESS_DEMOLISH_EVERY_MENU)])

    rows.append([_upgrade_button(UPGRADE_LEVEL, level, level_cost)])
    rows.append([_upgrade_button(UPGRADE_CAPACITY, capacity, capacity_cost)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def district_menu(
    district_id: int, *, can_build: bool, costs: dict[str, int] | None = None, has_buildings: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_build:
        rows.extend(
            [
                _btn(
                    BTN_BUILD.format(
                        name=BUSINESS_NAMES[type_],
                        cost=format_number((costs or BUSINESS_BUILD_COST)[type_]),
                    ),
                    f"{CB_BUSINESS_BUILD_PREFIX}{district_id}:{type_}",
                )
            ]
            for type_ in BUSINESS_TYPES
        )
    mass = []
    if can_build:
        mass.append(_btn(BTN_FILL, f"{CB_BUSINESS_FILL_MENU_PREFIX}{district_id}"))
    if has_buildings:
        mass.append(_btn(BTN_DEMOLISH, f"{CB_BUSINESS_DEMOLISH_MENU_PREFIX}{district_id}"))
    if mass:
        rows.append(mass)
    rows.append(
        [
            _btn(BTN_BACK_TO_BUSINESS, f"{CB_BUSINESS_PAGE_PREFIX}0"),
            _btn(BTN_TO_DISTRICT, f"{CB_DISTRICT_VIEW_PREFIX}{district_id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_from(district_id: int) -> InlineKeyboardButton:
    if district_id:
        return _btn(BTN_CANCEL, f"{CB_BUSINESS_DISTRICT_PREFIX}{district_id}")
    return _btn(BTN_BACK_TO_BUSINESS, f"{CB_BUSINESS_PAGE_PREFIX}0")


def fill_menu(district_id: int, costs: dict[str, int]) -> InlineKeyboardMarkup:
    """Выбор здания для «Застроить всё»; `district_id` 0 — все районы."""
    rows = [
        [_btn(BTN_FILL_TYPE.format(name=BUSINESS_NAMES[t], cost=format_number(costs[t])), f"{CB_BUSINESS_FILL_PREFIX}{district_id}:{t}")]
        for t in BUSINESS_TYPES
    ]
    rows.append([_back_from(district_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def demolish_menu(district_id: int, counts: dict[str, int]) -> InlineKeyboardMarkup:
    present = [t for t in BUSINESS_TYPES if counts.get(t)]
    rows = [
        [_btn(BTN_DEMOLISH_ONE.format(name=BUSINESS_NAMES[t]), f"{CB_BUSINESS_DEMOLISH_PREFIX}{district_id}:{t}") for t in present[i : i + 2]]
        for i in range(0, len(present), 2)
    ]
    if present:
        rows.append([_btn(BTN_DEMOLISH_ALL, f"{CB_BUSINESS_DEMOLISH_ALL_ASK_PREFIX}{district_id}")])
    rows.append([_back_from(district_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def demolish_confirm_menu(district_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_DEMOLISH_ALL_CONFIRM, f"{CB_BUSINESS_DEMOLISH_ALL_PREFIX}{district_id}")],
            [_btn(BTN_CANCEL, f"{CB_BUSINESS_DEMOLISH_MENU_PREFIX}{district_id}")],
        ]
    )


def demolish_everywhere_menu(counts: dict[str, int]) -> InlineKeyboardMarkup:
    """Снос во всех районах: по типу (сразу) или всё (через подтверждение)."""
    present = [t for t in BUSINESS_TYPES if counts.get(t)]
    rows = [
        [_btn(BTN_DEMOLISH_EVERY_TYPE.format(name=BUSINESS_NAMES[t], count=format_number(counts[t])), f"{CB_BUSINESS_DEMOLISH_EVERY_PREFIX}{t}")]
        for t in present
    ]
    if present:
        rows.append([_btn(BTN_DEMOLISH_EVERY_ALL.format(count=format_number(sum(counts.values()))), CB_BUSINESS_DEMOLISH_EVERY_ALL_ASK)])
    rows.append([_btn(BTN_BACK_TO_BUSINESS, CB_BUSINESS_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def demolish_everywhere_confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_DEMOLISH_ALL_CONFIRM, CB_BUSINESS_DEMOLISH_EVERY_ALL)],
            [_btn(BTN_CANCEL, CB_BUSINESS_DEMOLISH_EVERY_MENU)],
        ]
    )
