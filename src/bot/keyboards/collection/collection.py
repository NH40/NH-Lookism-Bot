"""Коллекция уникальных персонажей — список, карточка, распределение (клавиатуры)."""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.card import CARD_BY_CODE
from bot.constant.absolute import ABS_STYLIST, CB_STYLIST_PICK_PREFIX, STYLIST_CHOICES
from bot.texts.absolute import BTN_STYLIST_PICK
from bot.config.game import GANG_CAMP_MOVE_PERCENTS, GANG_SQUADS_PAGE_SIZE
from bot.constant.collection import (
    AMOUNT_ALL,
    AMOUNT_ONE,
    CB_COLLECTION_ASSIGN_PREFIX,
    CB_COLLECTION_CAMP_MOVE_PREFIX,
    CB_COLLECTION_CARD_PREFIX,
    CB_COLLECTION_MOVE_PREFIX,
    CB_COLLECTION_OPEN,
    CB_COLLECTION_PAGE_PREFIX,
)
from bot.constant.common import CB_NOOP
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.constant.gang import CB_GANG_BACK, CB_GANG_LINEUP
from bot.texts.card import POSITION_LABELS
from bot.texts.collection import (
    BTN_ASSIGN,
    BTN_BACK_TO_COLLECTION,
    BTN_BACK_TO_RARITIES,
    BTN_LINEUP,
    BTN_TO_ATTACK_ALL,
    BTN_TO_ATTACK_ONE,
    BTN_TO_DEFENSE_ALL,
    BTN_TO_DEFENSE_ONE,
)
from bot.texts.gang import BTN_BACK_TO_GANG, PERCENT_ALL_LABEL
from bot.texts.gang import BTN_TO_ATTACK as BTN_CAMP_TO_ATTACK, BTN_TO_DEFENSE as BTN_CAMP_TO_DEFENSE


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _camp_move_row(template: str, from_camp: str, to_camp: str) -> list[InlineKeyboardButton]:
    return [
        _btn(template.format(label=PERCENT_ALL_LABEL if p == 100 else f"{p}%"), f"{CB_COLLECTION_CAMP_MOVE_PREFIX}{from_camp}:{to_camp}:{p}")
        for p in GANG_CAMP_MOVE_PERCENTS
    ]


def rarities_menu(rarities: Sequence[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Экран коллекции: кнопка на каждую редкость, где у игрока есть карты (код, подпись), и
    быстрый перевод доли уников между лагерями — как у статистов на экране банды."""
    rows = [[_btn(label, f"{CB_COLLECTION_PAGE_PREFIX}{rarity}:0")] for rarity, label in rarities]
    if rarities:
        rows.append(_camp_move_row(BTN_CAMP_TO_DEFENSE, CAMP_ATTACK, CAMP_DEFENSE))
        rows.append(_camp_move_row(BTN_CAMP_TO_ATTACK, CAMP_DEFENSE, CAMP_ATTACK))
    rows.append([_btn(BTN_LINEUP, CB_GANG_LINEUP), _btn(BTN_BACK_TO_GANG, CB_GANG_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def collection_menu(cards: Sequence[tuple[str, str]], page: int, rarity: str) -> InlineKeyboardMarkup:
    """`cards` — карты одной редкости как (код, подпись), уже в порядке показа; страницу режет
    клавиатура (карт в каталоге ~160 — вся коллекция игрока одним запросом)."""
    size = GANG_SQUADS_PAGE_SIZE
    pages = max(1, (len(cards) + size - 1) // size)
    page = max(0, min(page, pages - 1))
    rows = [[_btn(label, f"{CB_COLLECTION_CARD_PREFIX}{code}")] for code, label in cards[page * size : (page + 1) * size]]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(_btn("◀️", f"{CB_COLLECTION_PAGE_PREFIX}{rarity}:{page - 1}"))
        nav.append(_btn(f"{page + 1}/{pages}", CB_NOOP))
        if page < pages - 1:
            nav.append(_btn("▶️", f"{CB_COLLECTION_PAGE_PREFIX}{rarity}:{page + 1}"))
        rows.append(nav)
    rows.append([_btn(BTN_BACK_TO_RARITIES, CB_COLLECTION_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def absolute_menu(code: str, *, rarity: str, pick: str | None) -> InlineKeyboardMarkup:
    """Абсолют: не воюет — лагерей и позиций нет. Стилист — выбор перка другого абсолюта."""
    rows = []
    if code == ABS_STYLIST:
        rows = [[_btn(BTN_STYLIST_PICK.format(mark="✅ " if c == pick else "", name=CARD_BY_CODE[c].name), f"{CB_STYLIST_PICK_PREFIX}{c}")]
                for c in STYLIST_CHOICES]
    rows.append([_btn(BTN_BACK_TO_COLLECTION, f"{CB_COLLECTION_PAGE_PREFIX}{rarity}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_menu(code: str, *, assignable: Sequence[str], rarity: str) -> InlineKeyboardMarkup:
    """Перенос копий между лагерями и постановка на позиции (`assignable` — допустимые
    позиции карты, куда её ещё можно поставить при свободной копии)."""
    move = f"{CB_COLLECTION_MOVE_PREFIX}{code}:"
    rows = [
        [_btn(BTN_TO_DEFENSE_ONE, f"{move}{CAMP_ATTACK}:{AMOUNT_ONE}"), _btn(BTN_TO_DEFENSE_ALL, f"{move}{CAMP_ATTACK}:{AMOUNT_ALL}")],
        [_btn(BTN_TO_ATTACK_ONE, f"{move}{CAMP_DEFENSE}:{AMOUNT_ONE}"), _btn(BTN_TO_ATTACK_ALL, f"{move}{CAMP_DEFENSE}:{AMOUNT_ALL}")],
    ]
    rows.extend(
        [_btn(BTN_ASSIGN.format(position=POSITION_LABELS[p]), f"{CB_COLLECTION_ASSIGN_PREFIX}{code}:{p}")]
        for p in assignable
    )
    rows.append([_btn(BTN_BACK_TO_COLLECTION, f"{CB_COLLECTION_PAGE_PREFIX}{rarity}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
