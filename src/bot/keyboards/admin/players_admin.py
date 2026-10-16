"""Админка: действия над игроком (выдача, развитие, наказания) — клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin.players_admin import CB_AST_MENU
from bot.config.development import MAX_LEVEL
from bot.constant.admin import CB_ADMIN_PLAYER_PREFIX
from bot.constant.admin.players_admin import (
    BAN_DURATIONS,
    BLOOD_NONE,
    CB_DEV_ACTIVE,
    CB_DEV_AWAKEN,
    CB_DEV_BLOOD,
    CB_DEV_BLOOD_LEVEL,
    CB_DEV_BLOOD_PICK,
    CB_DEV_BODY,
    CB_DEV_ITEM,
    CB_DEV_LEVEL,
    CB_DEV_LIST,
    CB_DEV_MENU,
    CB_DEV_MISC,
    CB_DEV_PASS,
    CB_DEV_POTENTIAL,
    CB_DEV_STATS,
    CB_DEV_STAT_PICK,
    CB_GIVE_CARD,
    CB_GIVE_MENU,
    CB_GIVE_RES_LIST,
    CB_GIVE_RES_PICK,
    CB_GIVE_SCROLLS,
    CB_GIVE_XP,
    CB_PUNISH_BAN,
    CB_PUNISH_BAN_DURATION,
    CB_PUNISH_BAN_NO_REASON,
    CB_PUNISH_COOLDOWNS,
    CB_PUNISH_DELETE_ASK,
    CB_PUNISH_DELETE_YES,
    CB_PUNISH_MENU,
    CB_PUNISH_RESET_ASK,
    CB_PUNISH_RESET_YES,
    CB_PUNISH_UNBAN,
)
from bot.constant.characteristic import POTENTIAL_ORDER, STATS
from bot.constant.resource import RESOURCES
from bot.texts.admin import players_admin as t
from bot.texts.resource import resource_label


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _rows(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def _back(data: str) -> list[InlineKeyboardButton]:
    return [_btn(t.BTN_BACK, data)]


def _card(uid: int) -> str:
    return f"{CB_ADMIN_PLAYER_PREFIX}{uid}"


def cancel_to(data: str) -> InlineKeyboardMarkup:
    """Одна кнопка «Назад» (под вводом текста)."""
    return InlineKeyboardMarkup(inline_keyboard=[_back(data)])


# ------------------------------- выдача -------------------------------
def give_menu(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [_btn(t.BTN_GIVE_RESOURCES, f"{CB_GIVE_RES_LIST}{uid}"), _btn(t.BTN_GIVE_STATIST, f"{CB_AST_MENU}{uid}")],
        [_btn(t.BTN_GIVE_CARD, f"{CB_GIVE_CARD}{uid}"), _btn(t.BTN_GIVE_SCROLLS, f"{CB_GIVE_SCROLLS}{uid}")],
        [_btn(t.BTN_GIVE_XP, f"{CB_GIVE_XP}{uid}")],
        _back(_card(uid)),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def give_resources(uid: int) -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_GIVE_RES_PICK}{code}:{uid}") for code in RESOURCES]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, 2) + [_back(f"{CB_GIVE_MENU}{uid}")])


# ------------------------------- развитие -------------------------------
def dev_menu(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [_btn(t.BTN_DEV_PATHS, f"{CB_DEV_LIST}path:{uid}"), _btn(t.BTN_DEV_TECHS, f"{CB_DEV_LIST}tech:{uid}")],
        [_btn(t.BTN_DEV_GENIUSES, f"{CB_DEV_LIST}gen:{uid}")],
        [_btn(t.BTN_DEV_BLOOD1, f"{CB_DEV_BLOOD}1:{uid}"), _btn(t.BTN_DEV_BLOOD2, f"{CB_DEV_BLOOD}2:{uid}")],
        [_btn(t.BTN_DEV_MISC, f"{CB_DEV_MISC}{uid}")],
        _back(_card(uid)),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dev_list(uid: int, kind: str, owned: dict[str, int], active: str | None) -> InlineKeyboardMarkup:
    buttons = []
    for idx, code in enumerate(t.DEV_CODES[kind]):
        mark = f" {'★' if code == active else ''}{owned[code]}" if code in owned else ""
        buttons.append(_btn(f"{t.DEV_NAMES[kind].get(code, code)}{mark}", f"{CB_DEV_ITEM}{kind}:{idx}:{uid}"))
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, 2) + [_back(f"{CB_DEV_MENU}{uid}")])


def dev_item(uid: int, kind: str, idx: int, owned: bool, is_active: bool) -> InlineKeyboardMarkup:
    levels = [_btn(str(n), f"{CB_DEV_LEVEL}{kind}:{idx}:{n}:{uid}") for n in range(1, MAX_LEVEL + 1)]
    rows = _rows(levels, 5)
    if owned:
        extra = [_btn(t.BTN_LEVEL_TAKE, f"{CB_DEV_LEVEL}{kind}:{idx}:0:{uid}")]
        if not is_active:
            extra.insert(0, _btn(t.BTN_MAKE_ACTIVE, f"{CB_DEV_ACTIVE}{kind}:{idx}:{uid}"))
        rows.append(extra)
    rows.append(_back(f"{CB_DEV_LIST}{kind}:{uid}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dev_bloodline(uid: int, slot: int, current: str | None) -> InlineKeyboardMarkup:
    buttons = [
        _btn(f"{'✅ ' if code == current else ''}{t.BLOODLINE_TITLES.get(code, code)}", f"{CB_DEV_BLOOD_PICK}{slot}:{idx}:{uid}")
        for idx, code in enumerate(t.BLOODLINE_CODES)
    ]
    rows = _rows(buttons, 2)
    if current:
        levels = [_btn(str(n), f"{CB_DEV_BLOOD_LEVEL}{slot}:{n}:{uid}") for n in range(1, MAX_LEVEL + 1)]
        rows += _rows(levels, 5)
        rows.append([_btn(t.BTN_BLOOD_NONE, f"{CB_DEV_BLOOD_PICK}{slot}:{BLOOD_NONE}:{uid}")])
    rows.append(_back(f"{CB_DEV_MENU}{uid}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dev_misc(uid: int, *, body: bool, premium: bool) -> InlineKeyboardMarkup:
    def state(on: bool) -> str:
        return t.STATE_ON if on else t.STATE_OFF

    rows = [
        [_btn(t.BTN_TOGGLE_BODY.format(state=state(body)), f"{CB_DEV_BODY}{uid}")],
        [_btn(t.BTN_TOGGLE_PASS.format(state=state(premium)), f"{CB_DEV_PASS}{uid}")],
        [_btn(t.BTN_AWAKENING, f"{CB_DEV_AWAKEN}-1:{uid}"), _btn(t.BTN_POTENTIAL, f"{CB_DEV_POTENTIAL}-1:{uid}")],
        [_btn(t.BTN_STATS, f"{CB_DEV_STATS}{uid}")],
        _back(f"{CB_DEV_MENU}{uid}"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dev_awakening(uid: int, max_level: int) -> InlineKeyboardMarkup:
    buttons = [_btn(str(n), f"{CB_DEV_AWAKEN}{n}:{uid}") for n in range(0, max_level + 1)]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, 6) + [_back(f"{CB_DEV_MISC}{uid}")])


def dev_potential(uid: int) -> InlineKeyboardMarkup:
    buttons = [_btn(code, f"{CB_DEV_POTENTIAL}{idx}:{uid}") for idx, code in enumerate(POTENTIAL_ORDER)]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, 2) + [_back(f"{CB_DEV_MISC}{uid}")])


def dev_stats(uid: int) -> InlineKeyboardMarkup:
    buttons = [_btn(t.STAT_NAMES.get(stat, stat), f"{CB_DEV_STAT_PICK}{stat}:{uid}") for stat in STATS]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, 2) + [_back(f"{CB_DEV_MISC}{uid}")])


# ------------------------------ наказания ------------------------------
def punish_menu(uid: int, banned: bool) -> InlineKeyboardMarkup:
    rows = [
        [_btn(t.BTN_UNBAN, f"{CB_PUNISH_UNBAN}{uid}") if banned else _btn(t.BTN_BAN, f"{CB_PUNISH_BAN}{uid}")],
        [_btn(t.BTN_COOLDOWNS, f"{CB_PUNISH_COOLDOWNS}{uid}")],
        [_btn(t.BTN_RESET, f"{CB_PUNISH_RESET_ASK}{uid}")],
        [_btn(t.BTN_DELETE, f"{CB_PUNISH_DELETE_ASK}{uid}")],
        _back(_card(uid)),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ban_durations(uid: int) -> InlineKeyboardMarkup:
    buttons = [_btn(t.BAN_DURATION_TITLES[key], f"{CB_PUNISH_BAN_DURATION}{key}:{uid}") for key in BAN_DURATIONS]
    return InlineKeyboardMarkup(inline_keyboard=_rows(buttons, 3) + [_back(f"{CB_PUNISH_MENU}{uid}")])


def ban_reason(uid: int, key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(t.BTN_NO_REASON, f"{CB_PUNISH_BAN_NO_REASON}{key}:{uid}")],
        _back(f"{CB_PUNISH_BAN}{uid}"),
    ])


def _confirm(uid: int, yes_prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(t.BTN_YES, f"{yes_prefix}{uid}")], [_btn(t.BTN_NO, f"{CB_PUNISH_MENU}{uid}")],
    ])


def reset_confirm(uid: int) -> InlineKeyboardMarkup:
    return _confirm(uid, CB_PUNISH_RESET_YES)


def delete_confirm(uid: int) -> InlineKeyboardMarkup:
    return _confirm(uid, CB_PUNISH_DELETE_YES)
