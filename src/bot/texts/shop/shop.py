"""Магазин (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML.
"""
from __future__ import annotations

SHOP_SCREEN = "🛍 <b>Магазин</b>\n━━━━━━━━━━━━━━━━━━\n🪙 NHCoin: <b>{coins}</b>\n━━━━━━━━━━━━━━━━━━\n{items}"
FREE_POINTS = "🥋 Невложенных очков мастерства: <b>{free}</b>"
BTN_TO_MASTERY = "🥋 Вложить очки"
TICKETS_LINE = "🎟 Тикеты: <b>{price}</b> NHCoin за штуку · сегодня ещё <b>{left}</b> из {limit}"
BTN_TICKETS = "🎟 ×{n}"
BTN_TICKETS_ALL = "🎟 Все {n}"
TICKETS_BOUGHT = "🎟 Куплено тикетов: {n} за {cost} NHCoin."
TICKETS_LIMIT = "Сегодня можно купить ещё {left} тикетов."
TICKETS_NO_COINS = "Не хватает NHCoin: нужно {cost}."
SHOP_BUSY = "Обрабатываю…"
