"""Battle Pass (клавиатуры): 2 строки по 5 ячеек — платная сверху, бесплатная снизу (как в UAP)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.admin.live_config import get as live_get
from bot.constant.battle_pass import (
    CB_BP_BUY_PREMIUM,
    CB_BP_CLAIM_ALL_PREFIX,
    CB_BP_CLAIM_PREFIX,
    CB_BP_PAGE_PREFIX,
    TRACK_FREE,
    TRACK_PREMIUM,
)
from bot.constant.common import CB_MENU_QUESTS, CB_NOOP
from bot.texts.battle_pass import (
    BTN_BUY_PREMIUM,
    BTN_CLAIM_ALL_FREE,
    BTN_CLAIM_ALL_PREMIUM,
    BTN_NEXT,
    BTN_PAGE,
    BTN_PREV,
    BTN_TO_QUESTS,
    CELL_CLAIMED,
    CELL_LOCKED,
    CELL_NO_PREMIUM,
    CELL_READY,
)


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _cell(page, entry, track: str) -> InlineKeyboardButton:
    claimed = entry.premium_claimed if track == TRACK_PREMIUM else entry.free_claimed
    if claimed:
        label = CELL_CLAIMED
    elif entry.level > page.level:
        label = CELL_LOCKED
    elif track == TRACK_PREMIUM and not page.is_premium:
        label = CELL_NO_PREMIUM
    else:
        label = CELL_READY
    return _btn(label.format(level=entry.level), f"{CB_BP_CLAIM_PREFIX}{track}:{entry.level}")


def pass_menu(page) -> InlineKeyboardMarkup:
    """`page` — `services.battle_pass.PassPage`."""
    rows = [
        [_cell(page, e, TRACK_PREMIUM) for e in page.entries],
        [_cell(page, e, TRACK_FREE) for e in page.entries],
        [
            _btn(BTN_PREV, f"{CB_BP_PAGE_PREFIX}{page.page - 1}") if page.page > 1 else _btn(" ", CB_NOOP),
            _btn(BTN_PAGE.format(page=page.page, pages=page.pages_max), CB_NOOP),
            _btn(BTN_NEXT, f"{CB_BP_PAGE_PREFIX}{page.page + 1}") if page.page < page.pages_max else _btn(" ", CB_NOOP),
        ],
    ]
    claim = []
    if page.unclaimed(TRACK_FREE):
        claim.append(_btn(BTN_CLAIM_ALL_FREE, f"{CB_BP_CLAIM_ALL_PREFIX}{TRACK_FREE}"))
    if page.unclaimed(TRACK_PREMIUM):
        claim.append(_btn(BTN_CLAIM_ALL_PREMIUM, f"{CB_BP_CLAIM_ALL_PREFIX}{TRACK_PREMIUM}"))
    if claim:
        rows.append(claim)
    if not page.is_premium:
        rows.append([_btn(BTN_BUY_PREMIUM.format(price=live_get("bp_premium_price")), CB_BP_BUY_PREMIUM)])
    rows.append([_btn(BTN_TO_QUESTS, CB_MENU_QUESTS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
