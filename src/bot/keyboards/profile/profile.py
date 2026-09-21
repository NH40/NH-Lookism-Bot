"""Экран «Профиль» (клавиатуры).

Главное меню — навигация по 7 вкладкам дизайна 2.0.0, прикреплена сюда по прямому
запросу пользователя 2026-09-21 ("чтобы игрок мог использовать все функции игры" через
бота, не только Mini App) — тот же список разделов, что нижняя навигация Mini App
(`src/web/src/constants`), плюс "🎯 Вербовка"/"🏋️ Тренировка" (реально рабочие
под-фичи без своего домена верхнего уровня — по дизайну обе живут внутри «Карты»/
«Банды», которых ещё нет). Разделы без реализованного домена ведут на честную заглушку
(`handlers/common`), не на выдуманный экран.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.constant.common import (
    CB_MENU_CLANS,
    CB_MENU_DEVELOPMENT,
    CB_MENU_MAP,
    CB_MENU_QUESTS,
    CB_MENU_SETTINGS,
    CB_MENU_SHOP,
)
from bot.constant.recruit import CB_RECRUIT_OPEN
from bot.constant.training import CB_TRAIN_EXTRAS_OPEN
from bot.utils.mini_app import mini_app_url as build_mini_app_url

BTN_PROFILE_APP = "🖼 Профиль (веб)"
BTN_MENU_MAP = "🗺 Карта"
BTN_MENU_DEVELOPMENT = "📈 Развитие"
BTN_MENU_SHOP = "🛍 Магазин"
BTN_MENU_CLANS = "👥 Кланы"
BTN_MENU_QUESTS = "📋 Задания"
BTN_MENU_SETTINGS = "⚙️ Настройки"
BTN_MENU_RECRUIT = "🎯 Вербовка"
BTN_MENU_TRAIN = "🏋️ Тренировка"


def profile_menu(*, mini_app_url: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if mini_app_url:
        rows.append(
            [InlineKeyboardButton(text=BTN_PROFILE_APP, web_app=WebAppInfo(url=build_mini_app_url(mini_app_url)))]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(text=BTN_MENU_MAP, callback_data=CB_MENU_MAP),
                InlineKeyboardButton(text=BTN_MENU_DEVELOPMENT, callback_data=CB_MENU_DEVELOPMENT),
            ],
            [
                InlineKeyboardButton(text=BTN_MENU_SHOP, callback_data=CB_MENU_SHOP),
                InlineKeyboardButton(text=BTN_MENU_CLANS, callback_data=CB_MENU_CLANS),
            ],
            [
                InlineKeyboardButton(text=BTN_MENU_QUESTS, callback_data=CB_MENU_QUESTS),
                InlineKeyboardButton(text=BTN_MENU_SETTINGS, callback_data=CB_MENU_SETTINGS),
            ],
            [
                InlineKeyboardButton(text=BTN_MENU_RECRUIT, callback_data=CB_RECRUIT_OPEN),
                InlineKeyboardButton(text=BTN_MENU_TRAIN, callback_data=CB_TRAIN_EXTRAS_OPEN),
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
