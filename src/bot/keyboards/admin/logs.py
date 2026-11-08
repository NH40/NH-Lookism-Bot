"""Админка — журналы (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup as M

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_PLAYER_PREFIX, CB_ADMIN_SECTION_PREFIX, SECTION_LOGS
from bot.constant.admin.logs import (
    CB_LG_AUDIT_FILTER,
    CB_LG_AUDIT_PREFIX,
    CB_LG_BM,
    CB_LG_CLAN_PREFIX,
    CB_LG_PAY_PREFIX,
    CB_LG_PLAYER_PREFIX,
    PL_ACTIVITY,
    CB_LG_BATTLE_PREFIX,
    CB_LG_BIG_PREFIX,
    CB_LG_ERR_PREFIX,
    CB_LG_ERV_PREFIX,
    CB_LG_SLOW_PREFIX,
    CB_LG_UPSET_PREFIX,
    PL_BATTLES,
    PL_CHANGES,
    PL_COINS,
    PL_GOODS,
    PL_AUDIT,
    PL_PAY,
)
from bot.texts.admin import logs as t
from bot.texts.admin.admin import BTN_BACK, BTN_BACK_TO_PLAYER

_SECTION = f"{CB_ADMIN_SECTION_PREFIX}{SECTION_LOGS}"


def menu() -> M:
    return M(inline_keyboard=[
        [B(text=t.BTN_AUDIT, callback_data=f"{CB_LG_AUDIT_PREFIX}0:0")],
        [B(text=t.BTN_PAY, callback_data=f"{CB_LG_PAY_PREFIX}0"), B(text=t.BTN_CLAN, callback_data=f"{CB_LG_CLAN_PREFIX}0")],
        [B(text=t.BTN_BM, callback_data=CB_LG_BM)],
        [B(text=t.BTN_ERRORS, callback_data=f"{CB_LG_ERR_PREFIX}0"), B(text=t.BTN_SLOW, callback_data=f"{CB_LG_SLOW_PREFIX}0")],
        [B(text=t.BTN_BIG, callback_data=f"{CB_LG_BIG_PREFIX}0"), B(text=t.BTN_UPSETS, callback_data=f"{CB_LG_UPSET_PREFIX}0")],
        [B(text=BTN_BACK, callback_data=CB_ADMIN_OPEN)],
    ])


def _nav(prefix: str, page: int, total: int, per: int, extra: str = "") -> list[B]:
    row = []
    if page > 0:
        row.append(B(text="◀️", callback_data=f"{prefix}{extra}{page - 1}"))
    if (page + 1) * per < total:
        row.append(B(text="▶️", callback_data=f"{prefix}{extra}{page + 1}"))
    return row


def back_to_menu() -> M:
    return M(inline_keyboard=[[B(text=t.BTN_BACK, callback_data=_SECTION)]])


def audit(admin_id: int, page: int, total: int, per: int) -> M:
    rows = []
    nav = _nav(CB_LG_AUDIT_PREFIX, page, total, per, extra=f"{admin_id}:")
    if nav:
        rows.append(nav)
    rows.append([B(text=t.BTN_FILTER, callback_data=CB_LG_AUDIT_FILTER)])
    rows.append([B(text=t.BTN_BACK, callback_data=_SECTION)])
    return M(inline_keyboard=rows)


def audit_filter(staff: list[tuple[int, str | None]]) -> M:
    rows = [[B(text=t.BTN_ALL, callback_data=f"{CB_LG_AUDIT_PREFIX}0:0")]]
    for uid, name in staff:
        rows.append([B(text=f"@{name}" if name else str(uid), callback_data=f"{CB_LG_AUDIT_PREFIX}{uid}:0")])
    rows.append([B(text=t.BTN_BACK, callback_data=_SECTION)])
    return M(inline_keyboard=rows)


def _battle_rows(ids: tuple[int, ...], uid: int) -> list[list[B]]:
    buttons = [B(text=f"#{i}", callback_data=f"{CB_LG_BATTLE_PREFIX}{i}:{uid}") for i in ids]
    return [buttons[i : i + 5] for i in range(0, len(buttons), 5)]


def upsets(page: int, total: int, per: int, ids: tuple[int, ...]) -> M:
    rows = _battle_rows(ids, 0)
    nav = _nav(CB_LG_UPSET_PREFIX, page, total, per)
    if nav:
        rows.append(nav)
    rows.append([B(text=t.BTN_BACK, callback_data=_SECTION)])
    return M(inline_keyboard=rows)


def errors(page: int, total: int, per: int, ids: tuple[int, ...]) -> M:
    buttons = [B(text=f"#{i}", callback_data=f"{CB_LG_ERV_PREFIX}{i}") for i in ids]
    rows = [buttons[i : i + 5] for i in range(0, len(buttons), 5)]
    nav = _nav(CB_LG_ERR_PREFIX, page, total, per)
    if nav:
        rows.append(nav)
    rows.append([B(text=t.BTN_BACK, callback_data=_SECTION)])
    return M(inline_keyboard=rows)


def back_to(callback_data: str) -> M:
    return M(inline_keyboard=[[B(text=t.BTN_BACK, callback_data=callback_data)]])


def paged(prefix: str, page: int, total: int, per: int) -> M:
    rows = []
    nav = _nav(prefix, page, total, per)
    if nav:
        rows.append(nav)
    rows.append([B(text=t.BTN_BACK, callback_data=_SECTION)])
    return M(inline_keyboard=rows)


def player(uid: int, kind: str, page: int, total: int, per: int, battle_ids: tuple[int, ...] = ()) -> M:
    tabs = [(t.BTN_TAB_AUDIT, PL_AUDIT), (t.BTN_TAB_PAY, PL_PAY), (t.BTN_TAB_ACT, PL_ACTIVITY), (t.BTN_TAB_COINS, PL_COINS), (t.BTN_TAB_GOODS, PL_GOODS), (t.BTN_TAB_CHANGES, PL_CHANGES), (t.BTN_TAB_BATTLES, PL_BATTLES)]
    buttons = [B(text=("• " if k == kind else "") + label, callback_data=f"{CB_LG_PLAYER_PREFIX}{uid}:{k}:0") for label, k in tabs]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    rows += _battle_rows(battle_ids, uid)
    nav = _nav(CB_LG_PLAYER_PREFIX, page, total, per, extra=f"{uid}:{kind}:")
    if nav:
        rows.append(nav)
    rows.append([B(text=BTN_BACK_TO_PLAYER, callback_data=f"{CB_ADMIN_PLAYER_PREFIX}{uid}")])
    return M(inline_keyboard=rows)
