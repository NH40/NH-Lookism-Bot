"""Бизнесы на районах (константы).

raw-notes «Карта» → «Бизнес»: Кофе, Тренажёрный зал, Магазин, Нелегальный рынок,
Парламент. Тип хранится в БД и сравнивается (подсчёт дохода по типам, callback'и
стройки) — константы, не литералы.
"""
from __future__ import annotations

BIZ_CAFE = "cafe"
BIZ_GYM = "gym"
BIZ_SHOP = "shop"
BIZ_BLACK_MARKET = "black_market"
BIZ_PARLIAMENT = "parliament"

BUSINESS_TYPES: tuple[str, ...] = (BIZ_CAFE, BIZ_SHOP, BIZ_BLACK_MARKET, BIZ_GYM, BIZ_PARLIAMENT)

# Прокачка — глобальная для игрока, не для отдельного здания (raw-notes: «за каждый
# уровень КАЖДОЕ здание будет приносить больше»; «вместимость — на 1 районе больше
# бизнесов»).
UPGRADE_LEVEL = "level"
UPGRADE_CAPACITY = "capacity"

CB_BUSINESS_OPEN = "biz:open"
CB_BUSINESS_PAGE_PREFIX = "biz:page:"
"""f"{CB_BUSINESS_PAGE_PREFIX}{page}" — экран бизнеса (редактированием на месте)."""
CB_BUSINESS_COLLECT = "biz:collect"
CB_BUSINESS_DISTRICT_PREFIX = "biz:district:"
CB_BUSINESS_BUILD_PREFIX = "biz:build:"
"""f"{CB_BUSINESS_BUILD_PREFIX}{district_id}:{type}"."""
CB_BUSINESS_UPGRADE_PREFIX = "biz:upgrade:"
"""f"{CB_BUSINESS_UPGRADE_PREFIX}{UPGRADE_LEVEL|UPGRADE_CAPACITY}"."""

CB_BUSINESS_FILL_MENU_PREFIX = "biz:fillm:"
"""f"{CB_BUSINESS_FILL_MENU_PREFIX}{district_id}" — выбор типа для «Застроить всё» (0 — все районы)."""
CB_BUSINESS_FILL_PREFIX = "biz:fill:"
"""f"{CB_BUSINESS_FILL_PREFIX}{district_id}:{type}" (district_id 0 — все районы)."""
CB_BUSINESS_DEMOLISH_MENU_PREFIX = "biz:demm:"
"""f"{CB_BUSINESS_DEMOLISH_MENU_PREFIX}{district_id}" — экран сноса."""
CB_BUSINESS_DEMOLISH_PREFIX = "biz:dem:"
"""f"{CB_BUSINESS_DEMOLISH_PREFIX}{district_id}:{type}" — снести одно здание."""
CB_BUSINESS_DEMOLISH_ALL_ASK_PREFIX = "biz:demaa:"
CB_BUSINESS_DEMOLISH_ALL_PREFIX = "biz:dema:"
"""f"{...}{district_id}" — снести всё на районе (сначала подтверждение)."""

# Правило 2: стройка и прокачка тратят NHCoin — один лок на оба действия (общий ресурс).
LOCK_ACTION_BUSINESS = "business"
