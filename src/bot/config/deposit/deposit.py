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
# 2026-11-20 (инфляция: вклады напечатали ~0,5 трлн за 13 дней) — ставки в 10 раз ниже (было 2/5/9/15/25%).
DEPOSIT_RATES: dict[int, float] = {1: 0.002, 3: 0.005, 6: 0.009, 12: 0.015, 24: 0.025}
# Остальные ресурсы — такая доля от ставки NHCoin.
DEPOSIT_OTHER_RATE_SHARE = 0.5
# Потолок вклада NHCoin — доход бизнеса за `DEPOSIT_COINS_CAP_HOURS` часов (не меньше `DEPOSIT_COINS_MIN_CAP`).
DEPOSIT_COINS_MIN_CAP = 20_000
DEPOSIT_COINS_CAP_HOURS = 6  # было 24 (суточный доход), 2026-11-20
# Потолки вклада остальных ресурсов.
DEPOSIT_CAPS: dict[str, int] = {
    RES_TICKETS: 50,
    RES_DEV_POINTS: 300,
    RES_PATH_POINTS: 2_000,
    RES_PATH_FRAGMENTS: 1_000,
    RES_TECHNIQUE_FRAGMENTS: 1_000,
    RES_GENIUS_FRAGMENTS: 1_000,
}
# Ресурсы, которые нельзя вкладывать (пользователь 2026-10-28: «убрать из инвестиций кровь»).
DEPOSIT_EXCLUDED: frozenset[str] = frozenset({RES_BLOOD})
