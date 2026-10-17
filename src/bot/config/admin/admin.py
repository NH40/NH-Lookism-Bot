"""Админ-панель — настраиваемые числа (не игровой баланс).

Бета-режим (2026-09-30, срочный запрос пользователя): пока включён, все не-админы перед
любым действием в боте вводят кодовое слово от админа.
"""
from __future__ import annotations

BETA_CODE_MIN_LENGTH = 3
BETA_CODE_MAX_LENGTH = 32
# Длина кода, который генерирует кнопка «🎲 Сгенерировать».
BETA_GENERATED_CODE_LENGTH = 8
# Защита от подбора: столько неверных попыток за окно — дальше ввод блокируется до конца окна.
BETA_MAX_ATTEMPTS = 10
BETA_ATTEMPTS_WINDOW_SECONDS = 3600


# --- Роли и права разделов админки (2026-10-08) ---
from bot.constant.admin import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_MODERATOR,
    ROLE_SUPER,
    ROLE_SUPPORT,
    SECTION_CLANS,
    SECTION_CONFIG,
    SECTION_DEV,
    SECTION_EVENTS,
    SECTION_GIVE,
    SECTION_LOGS,
    SECTION_MASS,
    SECTION_PATCH,
    SECTION_PLAYERS,
    SECTION_PROMO,
    SECTION_PUNISH,
    SECTION_REFERRAL,
    SECTION_ROLES,
    SECTION_SEASON,
    SECTION_STATS,
    SECTION_SYSTEM,
    SECTION_WORLD,
)

ROLE_LEVEL: dict[str, int] = {ROLE_SUPPORT: 1, ROLE_MODERATOR: 2, ROLE_ADMIN: 3, ROLE_SUPER: 4}
# Раздел → минимальная роль. Саппорт смотрит и отвечает игрокам, модератор наказывает и ведёт
# события, админ меняет экономику и мир, супер-админ — роли, патчи/вайп и настройки на лету.
SECTION_MIN_ROLE: dict[str, str] = {
    SECTION_PLAYERS: ROLE_SUPPORT,
    SECTION_STATS: ROLE_SUPPORT,
    SECTION_LOGS: ROLE_MODERATOR,
    SECTION_PUNISH: ROLE_MODERATOR,
    SECTION_EVENTS: ROLE_MODERATOR,
    SECTION_CLANS: ROLE_MODERATOR,
    SECTION_GIVE: ROLE_ADMIN,
    SECTION_DEV: ROLE_ADMIN,
    SECTION_MASS: ROLE_ADMIN,
    SECTION_PROMO: ROLE_ADMIN,
    SECTION_WORLD: ROLE_ADMIN,
    SECTION_SEASON: ROLE_ADMIN,
    SECTION_REFERRAL: ROLE_ADMIN,
    SECTION_SYSTEM: ROLE_ADMIN,
    SECTION_ROLES: ROLE_SUPER,
    SECTION_PATCH: ROLE_SUPER,
    SECTION_CONFIG: ROLE_SUPER,
}
# Порядок кнопок разделов в главном меню.
SECTION_ORDER: tuple[str, ...] = (
    SECTION_PLAYERS, SECTION_MASS, SECTION_PROMO, SECTION_STATS, SECTION_LOGS, SECTION_WORLD,
    SECTION_EVENTS, SECTION_CLANS, SECTION_SEASON, SECTION_REFERRAL, SECTION_ROLES, SECTION_PATCH,
    SECTION_CONFIG, SECTION_SYSTEM,
)
ADMIN_AUDIT_PAGE = 15  # записей журнала на страницу
# Как часто бот и API перечитывают настройки на лету (правка из другого процесса — с этой задержкой).
LIVE_CONFIG_REFRESH_SECONDS = 15
