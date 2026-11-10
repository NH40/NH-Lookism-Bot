"""Магазин (константы).

Вход — кнопка «🛍 Магазин» в меню профиля (`constant/common.CB_MENU_SHOP`). Тренер Том Ли
(очки мастерства) убран 2026-11-10.
"""
from __future__ import annotations

# Правило 2: покупка тратит NHCoin — Redis-лок на клик.
LOCK_ACTION_SHOP = "shop"
