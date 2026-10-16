"""Биржа (константы)."""
from __future__ import annotations

MODE_LOT = "lot"
MODE_AUCTION = "auc"
MODE_TRADE = "trade"

CB_EXCHANGE_OPEN = "ex:open"
CB_EXCHANGE_LOTS_PREFIX = "ex:lots:"  # f"{...}{page}" — лоты на продажу
CB_EXCHANGE_LOT_PREFIX = "ex:lot:"  # f"{...}{id}" — карточка лота
CB_EXCHANGE_BUY_PREFIX = "ex:buy:"  # f"{...}{id}"
CB_EXCHANGE_AUCTIONS_PREFIX = "ex:aucs:"  # f"{...}{page}"
CB_EXCHANGE_AUCTION_PREFIX = "ex:auc:"  # f"{...}{id}"
CB_EXCHANGE_BID_PREFIX = "ex:bid:"  # f"{...}{id}:{amount}" — ставка (amount 0 — ввести свою)
CB_EXCHANGE_MINE = "ex:mine"  # мои лоты, аукционы, обмены
CB_EXCHANGE_CANCEL_LOT_PREFIX = "ex:cl:"  # f"{...}{id}"
CB_EXCHANGE_CANCEL_AUCTION_PREFIX = "ex:ca:"  # f"{...}{id}" — только без ставок
CB_EXCHANGE_TRADE_ACCEPT_PREFIX = "ex:ta:"  # f"{...}{id}"
CB_EXCHANGE_TRADE_DECLINE_PREFIX = "ex:td:"  # f"{...}{id}" — отказ получателя или отзыв автором
# Мастер предложения (лот / аукцион / обмен): шаги — в данных FSM.
CB_EXCHANGE_NEW_PREFIX = "ex:new:"  # f"{...}{mode}" — выбрать предмет
CB_EXCHANGE_ITEM_RES_PREFIX = "ex:ir:"  # f"{...}{resource}"
CB_EXCHANGE_ITEM_STATISTS = "ex:is"  # выбрать отряд
CB_EXCHANGE_ITEM_SQUAD_PREFIX = "ex:iq:"  # f"{...}{StatistKey}"
CB_EXCHANGE_PRICE_RES_PREFIX = "ex:pr:"  # f"{...}{resource}" — в чём цена
CB_EXCHANGE_HOURS_PREFIX = "ex:h:"  # f"{...}{hours}" — срок аукциона
CB_EXCHANGE_CONFIRM = "ex:ok"
# Правило 2: сделки двигают ресурсы — Redis-лок на клик.
LOCK_ACTION_EXCHANGE = "exchange"
