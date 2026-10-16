"""Админка — статистика (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_STATS
from bot.constant.admin.stats import CB_ST_DONATE, CB_ST_ECONOMY, CB_ST_OVERVIEW, CB_ST_SERVER
from bot.texts.admin import stats as t
from bot.texts.admin.admin import BTN_BACK

_SUB = [(t.BTN_OVERVIEW, CB_ST_OVERVIEW), (t.BTN_DONATE, CB_ST_DONATE), (t.BTN_ECONOMY, CB_ST_ECONOMY), (t.BTN_SERVER, CB_ST_SERVER)]


def menu() -> M:
    rows = [[B(text=_SUB[i][0], callback_data=_SUB[i][1]), B(text=_SUB[i + 1][0], callback_data=_SUB[i + 1][1])] for i in (0, 2)]
    rows.append([B(text=BTN_BACK, callback_data=CB_ADMIN_OPEN)])
    return M(inline_keyboard=rows)


def back() -> M:
    return M(inline_keyboard=[[B(text=t.BTN_BACK, callback_data=f"{CB_ADMIN_SECTION_PREFIX}{SECTION_STATS}")]])
