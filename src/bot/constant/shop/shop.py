"""Магазин (константы).

Вход — кнопка «🛍 Магазин» в меню профиля (`constant/common.CB_MENU_SHOP`). Первый товар —
тренер Том Ли (очки мастерства), появляется после победы над Томом в цепочке мастерства.
"""
from __future__ import annotations

CB_SHOP_BUY_MASTERY_POINT = "shop:mastery:buy"
# Правило 2: покупка тратит NHCoin — Redis-лок на клик.
LOCK_ACTION_SHOP = "shop"
