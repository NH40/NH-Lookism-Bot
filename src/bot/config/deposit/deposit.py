"""Вклады (конфиг).

Перенос из 1.0 («Банк → Инвестиции»: вклад ресурса на срок под процент, до 3 вкладов).
Пользователь 2026-10-04 выбрал «умеренно»: проценты ниже 1.0 (там NHCoin давал до +80% за
сутки) и лимит суммы от дохода — чтобы вклады не стали главным заработком вместо бизнеса.
Числа — решение автора кода.
"""
from __future__ import annotations

from bot.constant.resource import (
    RES_BLOOD,
    RES_DEV_POINTS,
    RES_GENIUS_FRAGMENTS,
    RES_PATH_FRAGMENTS,
    RES_PATH_POINTS,
    RES_TECHNIQUE_FRAGMENTS,
    RES_TICKETS,
)

DEPOSIT_MAX_ACTIVE = 3
# Срок (часы) → доходность NHCoin.
DEPOSIT_RATES: dict[int, float] = {1: 0.02, 3: 0.05, 6: 0.09, 12: 0.15, 24: 0.25}
# Остальные ресурсы — такая доля от ставки NHCoin.
DEPOSIT_OTHER_RATE_SHARE = 0.5
# Потолок вклада NHCoin — суточный доход бизнеса (не меньше этого).
DEPOSIT_COINS_MIN_CAP = 20_000
# Потолки вклада остальных ресурсов.
DEPOSIT_CAPS: dict[str, int] = {
    RES_TICKETS: 50,
    RES_DEV_POINTS: 300,
    RES_PATH_POINTS: 2_000,
    RES_PATH_FRAGMENTS: 1_000,
    RES_TECHNIQUE_FRAGMENTS: 1_000,
    RES_GENIUS_FRAGMENTS: 1_000,
    RES_BLOOD: 30,
}
