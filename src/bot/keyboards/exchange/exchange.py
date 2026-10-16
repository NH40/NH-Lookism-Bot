"""Биржа (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.exchange import EXCHANGE_AUCTION_HOURS
from bot.constant.common import CB_MENU_SHOP
from bot.constant.exchange import (
    CB_EXCHANGE_AUCTION_PREFIX,
    CB_EXCHANGE_AUCTIONS_PREFIX,
    CB_EXCHANGE_BID_PREFIX,
    CB_EXCHANGE_BUY_PREFIX,
    CB_EXCHANGE_CANCEL_AUCTION_PREFIX,
    CB_EXCHANGE_CANCEL_LOT_PREFIX,
    CB_EXCHANGE_CONFIRM,
    CB_EXCHANGE_HOURS_PREFIX,
    CB_EXCHANGE_ITEM_RES_PREFIX,
    CB_EXCHANGE_ITEM_SQUAD_PREFIX,
    CB_EXCHANGE_ITEM_STATISTS,
    CB_EXCHANGE_LOT_PREFIX,
    CB_EXCHANGE_LOTS_PREFIX,
    CB_EXCHANGE_MINE,
    CB_EXCHANGE_NEW_PREFIX,
    CB_EXCHANGE_OPEN,
    CB_EXCHANGE_PRICE_RES_PREFIX,
    CB_EXCHANGE_TRADE_ACCEPT_PREFIX,
    CB_EXCHANGE_TRADE_DECLINE_PREFIX,
    MODE_AUCTION,
    MODE_LOT,
    MODE_TRADE,
)
from bot.constant.resource import RESOURCES
from bot.texts.common import BTN_BACK
from bot.texts.exchange import (
    BTN_AUCTION,
    BTN_AUCTIONS,
    BTN_BID_CUSTOM,
    BTN_BID_MIN,
    BTN_BUY,
    BTN_CANCEL_AUCTION,
    BTN_CANCEL_LOT,
    BTN_CONFIRM,
    BTN_HOURS,
    BTN_ITEM_STATISTS,
    BTN_LOT,
    BTN_LOTS,
    BTN_MINE,
    BTN_NEW_AUCTION,
    BTN_NEW_LOT,
    BTN_NEW_TRADE,
    BTN_NEXT,
    BTN_PREV,
    BTN_SQUAD,
    BTN_TRADE_ACCEPT,
    BTN_TRADE_CANCEL,
    BTN_TRADE_DECLINE,
)
from bot.texts.resource import amount_label, item_amount_label, resource_label
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _back(callback: str = CB_EXCHANGE_OPEN) -> list[InlineKeyboardButton]:
    return [_btn(BTN_BACK, callback)]


def exchange_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_LOTS, f"{CB_EXCHANGE_LOTS_PREFIX}0"), _btn(BTN_AUCTIONS, f"{CB_EXCHANGE_AUCTIONS_PREFIX}0")],
            [_btn(BTN_NEW_LOT, f"{CB_EXCHANGE_NEW_PREFIX}{MODE_LOT}"), _btn(BTN_NEW_AUCTION, f"{CB_EXCHANGE_NEW_PREFIX}{MODE_AUCTION}")],
            [_btn(BTN_NEW_TRADE, f"{CB_EXCHANGE_NEW_PREFIX}{MODE_TRADE}")],
            [_btn(BTN_MINE, CB_EXCHANGE_MINE)],
            _back(CB_MENU_SHOP),
        ]
    )


def _pages(prefix: str, page: int, more: bool) -> list[InlineKeyboardButton]:
    nav = []
    if page > 0:
        nav.append(_btn(BTN_PREV, f"{prefix}{page - 1}"))
    if more:
        nav.append(_btn(BTN_NEXT, f"{prefix}{page + 1}"))
    return nav


def lots_menu(lots: list, page: int, more: bool) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_LOT.format(id=l.id, item=item_amount_label(l.item_kind, l.item_code, l.amount), price=amount_label(l.price_res, l.price)), f"{CB_EXCHANGE_LOT_PREFIX}{l.id}")]
        for l in lots
    ]
    nav = _pages(CB_EXCHANGE_LOTS_PREFIX, page, more)
    if nav:
        rows.append(nav)
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lot_menu(lot) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_BUY.format(price=amount_label(lot.price_res, lot.price)), f"{CB_EXCHANGE_BUY_PREFIX}{lot.id}")],
            _back(f"{CB_EXCHANGE_LOTS_PREFIX}0"),
        ]
    )


def auctions_menu(auctions: list, page: int, more: bool, bid_of) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_AUCTION.format(id=a.id, item=item_amount_label(a.item_kind, a.item_code, a.amount), bid=amount_label(a.price_res, bid_of(a))), f"{CB_EXCHANGE_AUCTION_PREFIX}{a.id}")]
        for a in auctions
    ]
    nav = _pages(CB_EXCHANGE_AUCTIONS_PREFIX, page, more)
    if nav:
        rows.append(nav)
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def auction_menu(auction, min_next: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_BID_MIN.format(amount=amount_label(auction.price_res, min_next)), f"{CB_EXCHANGE_BID_PREFIX}{auction.id}:{min_next}")],
            [_btn(BTN_BID_CUSTOM, f"{CB_EXCHANGE_BID_PREFIX}{auction.id}:0")],
            _back(f"{CB_EXCHANGE_AUCTIONS_PREFIX}0"),
        ]
    )


def mine_menu(lots: list, incoming: list, outgoing: list, auctions: list = ()) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_CANCEL_LOT.format(id=l.id), f"{CB_EXCHANGE_CANCEL_LOT_PREFIX}{l.id}")] for l in lots]
    rows.extend(
        [_btn(BTN_CANCEL_AUCTION.format(id=a.id), f"{CB_EXCHANGE_CANCEL_AUCTION_PREFIX}{a.id}")] for a in auctions if a.bidder_id is None
    )
    for t in incoming:
        rows.append([
            _btn(BTN_TRADE_ACCEPT.format(id=t.id), f"{CB_EXCHANGE_TRADE_ACCEPT_PREFIX}{t.id}"),
            _btn(BTN_TRADE_DECLINE.format(id=t.id), f"{CB_EXCHANGE_TRADE_DECLINE_PREFIX}{t.id}"),
        ])
    rows.extend([_btn(BTN_TRADE_CANCEL.format(id=t.id), f"{CB_EXCHANGE_TRADE_DECLINE_PREFIX}{t.id}")] for t in outgoing)
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def trade_offer_menu(trade_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            _btn(BTN_TRADE_ACCEPT.format(id=trade_id), f"{CB_EXCHANGE_TRADE_ACCEPT_PREFIX}{trade_id}"),
            _btn(BTN_TRADE_DECLINE.format(id=trade_id), f"{CB_EXCHANGE_TRADE_DECLINE_PREFIX}{trade_id}"),
        ]]
    )


def item_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_EXCHANGE_ITEM_RES_PREFIX}{code}") for code in RESOURCES]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_ITEM_STATISTS, CB_EXCHANGE_ITEM_STATISTS)])
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def squads_menu(squads: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_SQUAD.format(title=title, total=format_number(total)), f"{CB_EXCHANGE_ITEM_SQUAD_PREFIX}{key}")] for key, title, total in squads]
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def price_res_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_EXCHANGE_PRICE_RES_PREFIX}{code}") for code in RESOURCES]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hours_menu() -> InlineKeyboardMarkup:
    row = [_btn(BTN_HOURS.format(hours=h), f"{CB_EXCHANGE_HOURS_PREFIX}{h}") for h in EXCHANGE_AUCTION_HOURS]
    return InlineKeyboardMarkup(inline_keyboard=[row, _back()])


def confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_CONFIRM, CB_EXCHANGE_CONFIRM)], _back()])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_back()])
