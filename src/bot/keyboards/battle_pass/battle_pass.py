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
    from bot.constant.battle_pass import CB_BP_LEVELS
    from bot.texts.battle_pass.battle_pass import BTN_BUY_LEVELS

    rows.append([_btn(BTN_BUY_LEVELS, CB_BP_LEVELS), _btn(BTN_TO_QUESTS, CB_MENU_QUESTS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def levels_menu(room: int) -> InlineKeyboardMarkup:
    """Пресеты покупки уровней (не больше, чем осталось до конца пасса)."""
    from bot.config.battle_pass import BP_BUY_MIN_LEVELS, BP_BUY_PRESETS, BP_LEVEL_PRICE
    from bot.constant.battle_pass import CB_BP_LEVELS_BUY_PREFIX, CB_BP_OPEN
    from bot.texts.battle_pass.battle_pass import BTN_BACK_TO_PASS, BTN_LEVELS_PRESET

    counts = [n for n in BP_BUY_PRESETS if BP_BUY_MIN_LEVELS <= n <= room]
    if room >= BP_BUY_MIN_LEVELS and room not in counts and room < max(BP_BUY_PRESETS) * 2:
        counts.append(room)  # «до конца пасса»
    buttons = [_btn(BTN_LEVELS_PRESET.format(count=n, price=n * BP_LEVEL_PRICE), f"{CB_BP_LEVELS_BUY_PREFIX}{n}") for n in counts]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK_TO_PASS, CB_BP_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
