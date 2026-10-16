"""Админ-панель (константы)."""
from __future__ import annotations

CB_ADMIN_OPEN = "admin:open"
CB_ADMIN_TECH_TOGGLE = "admin:tech"

# Бета-режим.
CB_ADMIN_BETA_ON = "admin:beta:on"
CB_ADMIN_BETA_CODE = "admin:beta:code"  # сменить код, не сбрасывая уже допущенных
CB_ADMIN_BETA_GENERATE = "admin:beta:gen"
CB_ADMIN_BETA_OFF_ASK = "admin:beta:offask"
CB_ADMIN_BETA_OFF = "admin:beta:off"

# Что делает введённый/сгенерированный код — в FSM-данных промпта.
BETA_CODE_MODE_KEY = "beta_code_mode"
BETA_CODE_MODE_ENABLE = "enable"
BETA_CODE_MODE_CHANGE = "change"

# --- Админ-система 2.0 (пользователь 2026-10-08: «максимально большая админка») ---
# Роли: супер-админ — ADMIN_IDS из .env; остальные — `users.admin_role`.
ROLE_SUPER = "super"
ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"
ROLE_SUPPORT = "support"
ROLES = (ROLE_SUPPORT, ROLE_MODERATOR, ROLE_ADMIN)  # выдаваемые (супер — только через .env)

# Разделы админки (права — `config/admin.SECTION_MIN_ROLE`).
SECTION_PLAYERS = "players"  # поиск и карточка игрока
SECTION_GIVE = "give"  # выдать/забрать что угодно
SECTION_DEV = "dev"  # развитие игрока
SECTION_PUNISH = "punish"  # баны, сброс, удаление
SECTION_MASS = "mass"  # рассылка и массовая выдача
SECTION_PROMO = "promo"
SECTION_STATS = "stats"
SECTION_LOGS = "logs"  # журналы и аудит
SECTION_WORLD = "world"  # районы, города, императоры
SECTION_EVENTS = "events"  # события карты, ивенты, множители
SECTION_CLANS = "clans"
SECTION_SEASON = "season"  # сезон пасса и задания
SECTION_ROLES = "roles"
SECTION_PATCH = "patch"  # патчи и вайп
SECTION_CONFIG = "config"  # настройки на лету
SECTION_REFERRAL = "referral"
SECTION_SYSTEM = "system"  # бета-режим и техрежим

# Корень раздела: f"{CB_ADMIN_SECTION_PREFIX}{section}" — каждый раздел обрабатывает свой.
CB_ADMIN_SECTION_PREFIX = "adm:s:"
# Карточка игрока и действия над ним: префикс + id игрока.
CB_ADMIN_FIND = "adm:find"
CB_ADMIN_PLAYER_PREFIX = "adm:p:"
CB_ADMIN_PLAYER_GIVE_PREFIX = "adm:pg:"
CB_ADMIN_PLAYER_DEV_PREFIX = "adm:pd:"
CB_ADMIN_PLAYER_PUNISH_PREFIX = "adm:pp:"
CB_ADMIN_PLAYER_LOG_PREFIX = "adm:pl:"
CB_ADMIN_PLAYER_QUESTS_PREFIX = "adm:pq:"  # f"{...}{uid}" — задания игрока
CB_ADMIN_QUEST_DAILY_PREFIX = "adm:pqd:"  # f"{...}{slot}:{uid}" — засчитать ежедневное
CB_ADMIN_QUEST_DEV_PREFIX = "adm:pqx:"  # f"{...}{quest_id}:{uid}" — засчитать квест развития
CB_ADMIN_QUEST_ALL_PREFIX = "adm:pqa:"  # f"{...}{uid}" — засчитать все
