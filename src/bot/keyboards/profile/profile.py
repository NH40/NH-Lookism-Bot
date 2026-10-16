"""Экран «Профиль» (клавиатуры).

Главное меню — навигация по вкладкам дизайна 2.0.0, прикреплена к профилю по прямому
запросу пользователя 2026-09-21 ("чтобы игрок мог использовать все функции игры" через
бота, не только Mini App). Рабочие разделы — сверху (Карта/Банда/Бизнес/Вербовка/Тренировка),
разделы без реализованного домена — ниже, ведут на честную заглушку (`handlers/common`).
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.constant.common import CB_MENU_CLANS, CB_MENU_DEVELOPMENT, CB_MENU_QUESTS, CB_MENU_SETTINGS, CB_MENU_SHOP
from bot.constant.business import CB_BUSINESS_OPEN
from bot.constant.characteristic import CB_STATS_OPEN, CB_STATS_UP_PREFIX, STATS_UP_FIVE, STATS_UP_MAX, STATS_UP_ONE
from bot.constant.empire import CB_EMPIRE_OPEN, CB_SABOTAGE_OPEN
from bot.constant.mastery import CB_MASTERY_OPEN
from bot.constant.profile import CB_PROFILE_OPEN
from bot.constant.training import CB_TRAIN_PERSONAL
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.empire import BTN_EMPIRE, BTN_SABOTAGE
from bot.texts.profile import BTN_PERSONAL_TRAINING, BTN_STAT_UP_FIVE, BTN_STAT_UP_MAX, BTN_STAT_UP_ONE, BTN_STATS, STAT_LABELS
from bot.constant.gang import CB_GANG_OPEN
from bot.constant.map import CB_MAP_OPEN
from bot.constant.recruit import CB_RECRUIT_OPEN
from bot.constant.training import CB_TRAIN_EXTRAS_OPEN
from bot.utils.mini_app import mini_app_url as build_mini_app_url

BTN_PROFILE_APP = "🖼 Профиль (веб)"
BTN_MENU_MAP = "🗺 Карта"
BTN_MENU_GANG = "🏴 Банда"
BTN_MASTERY = "🥋 Мастерство"
BTN_MENU_BUSINESS = "💼 Бизнес"
BTN_MENU_RECRUIT = "🎯 Вербовка"
BTN_MENU_TRAIN = "🏋️ Тренировка"
BTN_MENU_DEVELOPMENT = "📈 Развитие"
BTN_MENU_SHOP = "🛍 Магазин"
BTN_MENU_CLANS = "👥 Кланы"
BTN_MENU_QUESTS = "📋 Задания"
BTN_MENU_SETTINGS = "⚙️ Настройки"


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def profile_menu(
    *, mini_app_url: str | None = None, emperor: bool = False, under_emperor: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if mini_app_url:
        rows.append(
            [InlineKeyboardButton(text=BTN_PROFILE_APP, web_app=WebAppInfo(url=build_mini_app_url(mini_app_url)))]
        )
    rows.extend(
        [
            [_btn(BTN_STATS, CB_STATS_OPEN), _btn(BTN_MASTERY, CB_MASTERY_OPEN)],
            [_btn(BTN_MENU_MAP, CB_MAP_OPEN), _btn(BTN_MENU_GANG, CB_GANG_OPEN)],
            [_btn(BTN_MENU_BUSINESS, CB_BUSINESS_OPEN), _btn(BTN_MENU_RECRUIT, CB_RECRUIT_OPEN)],
            [_btn(BTN_MENU_TRAIN, CB_TRAIN_EXTRAS_OPEN), _btn(BTN_MENU_DEVELOPMENT, CB_MENU_DEVELOPMENT)],
            [_btn(BTN_MENU_SHOP, CB_MENU_SHOP), _btn(BTN_MENU_CLANS, CB_MENU_CLANS)],
            [_btn(BTN_MENU_QUESTS, CB_MENU_QUESTS), _btn(BTN_MENU_SETTINGS, CB_MENU_SETTINGS)],
        ]
    )
    # Экран империи — только императору (права всё равно перепроверяет сервис).
    if emperor:
        rows.append([_btn(BTN_EMPIRE, CB_EMPIRE_OPEN)])
    # Саботаж — подданным чужого императора (игрок города, где император не он).
    if under_emperor:
        rows.append([_btn(BTN_SABOTAGE, CB_SABOTAGE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stats_menu(stats: list[tuple[str, bool]]) -> InlineKeyboardMarkup:
    """`stats` — (код характеристики, можно ли ещё поднимать). На каждую — «+1», «+5», «Макс»
    (сколько хватит очков); характеристика на Infinity — без кнопок."""
    rows = []
    for code, can_grow in stats:
        if not can_grow:
            continue
        prefix = f"{CB_STATS_UP_PREFIX}{code}:"
        rows.append(
            [
                _btn(BTN_STAT_UP_ONE.format(label=STAT_LABELS[code]), f"{prefix}{STATS_UP_ONE}"),
                _btn(BTN_STAT_UP_FIVE, f"{prefix}{STATS_UP_FIVE}"),
                _btn(BTN_STAT_UP_MAX, f"{prefix}{STATS_UP_MAX}"),
            ]
        )
    rows.append([_btn(BTN_PERSONAL_TRAINING, CB_TRAIN_PERSONAL)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
