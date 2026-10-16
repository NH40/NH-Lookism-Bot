"""Промокоды (константы): режимы создания."""
from __future__ import annotations

PROMO_MODE_USES = "uses"  # лимит активаций
PROMO_MODE_TIME = "time"  # срок действия в часах
PROMO_MODE_USERS = "users"  # список разрешённых @username через запятую
PROMO_MODES: tuple[str, ...] = (PROMO_MODE_USES, PROMO_MODE_TIME, PROMO_MODE_USERS)

PROMO_LIST_LIMIT = 20
PROMO_CODE_MAX_LEN = 32
