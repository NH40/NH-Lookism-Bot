"""Родословная Пеньгуана (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.penguan import PG_BUY_PRESETS
from bot.constant.bloodline import CB_BLOODLINE_SCREEN
from bot.constant.penguan import (
    CB_PG_BUFF_PREFIX,
    CB_PG_BUILDER,
    CB_PG_BUY_PREFIX,
    CB_PG_BUYBACK,
    CB_PG_BUYOUT,
    CB_PG_OPEN,
    CB_PG_SET_PREFIX,
    P_LEVEL,
    P_RANK,
    P_SCHOOL,
    P_SCHOOL_LEVEL,
    P_STARS,
)
from bot.texts.penguan import BTN_BACK, BTN_BUFF, BTN_BUILDER, BTN_BUY, BTN_BUYBACK, BTN_BUYOUT, BUFF_NAMES
from bot.utils.formatting import format_number


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu(buffs, *, builder: bool, buyback_price: int | None, buyout_price: int | None) -> InlineKeyboardMarkup:
    rows = [[_b(BTN_BUFF.format(name=BUFF_NAMES[o.kind], price=format_number(o.price)), f"{CB_PG_BUFF_PREFIX}{o.kind}")] for o in buffs]
    if builder:
        rows.append([_b(BTN_BUILDER, CB_PG_BUILDER)])
    if buyback_price is not None:
        rows.append([_b(BTN_BUYBACK.format(price=format_number(buyback_price)), CB_PG_BUYBACK)])
    if buyout_price is not None:
        rows.append([_b(BTN_BUYOUT.format(price=format_number(buyout_price)), CB_PG_BUYOUT)])
    rows.append([_b(BTN_BACK, CB_BLOODLINE_SCREEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _step(label: str, param: str) -> list[InlineKeyboardButton]:
    return [_b("−", f"{CB_PG_SET_PREFIX}{param}:-1"), _b(label, f"{CB_PG_SET_PREFIX}{param}:0"), _b("+", f"{CB_PG_SET_PREFIX}{param}:1")]


def builder_menu(max_units: int) -> InlineKeyboardMarkup:
    rows = [
        _step("Ранг", P_RANK),
        [_b("−10", f"{CB_PG_SET_PREFIX}{P_LEVEL}:-10"), *_step("Уровень", P_LEVEL), _b("+10", f"{CB_PG_SET_PREFIX}{P_LEVEL}:10")],
        _step("⭐ Звёзды", P_STARS),
        _step("Школа", P_SCHOOL),
        _step("Ур. школы", P_SCHOOL_LEVEL),
    ]
    buys = [_b(BTN_BUY.format(n=format_number(n)), f"{CB_PG_BUY_PREFIX}{n}") for n in PG_BUY_PRESETS if n <= max_units]
    if max_units and (not buys or max_units not in PG_BUY_PRESETS):
        buys.append(_b(BTN_BUY.format(n=format_number(max_units)), f"{CB_PG_BUY_PREFIX}{max_units}"))
    for i in range(0, len(buys), 3):
        rows.append(buys[i : i + 3])
    rows.append([_b(BTN_BACK, CB_PG_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
