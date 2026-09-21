"""Общее reply-меню бота (константы)."""
from __future__ import annotations

CB_NOOP = "noop"
"""Кнопка-индикатор без действия (например, номер страницы пагинации) — единая точка,
чтобы не разбредались строки-заглушки по клавиатурам разных доменов (см.
`handlers/common`, единственный хендлер, который на неё отвечает)."""

# Главное меню (см. keyboards/profile.profile_menu — навигация по 7 вкладкам дизайна
# 2.0.0, прикреплена к экрану профиля по прямому запросу пользователя 2026-09-21:
# "чтобы игрок мог использовать все функции игры" через бота, не только Mini App).
# Разделы без реализованного домена — честные заглушки (тот же принцип, что
# PlaceholderPage в Mini App, см. CLAUDE.md), не выдуманные механики/кнопки.
CB_MENU_MAP = "menu:map"
CB_MENU_DEVELOPMENT = "menu:development"
CB_MENU_SHOP = "menu:shop"
CB_MENU_CLANS = "menu:clans"
CB_MENU_QUESTS = "menu:quests"
CB_MENU_SETTINGS = "menu:settings"
