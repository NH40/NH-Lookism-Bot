"""«Пятницы» (пользователь 2026-11-12, идеи игроков): админ запускает одну пятницу, через
`SALE_HOURS` она заканчивается сама, выключить можно раньше. Только одна одновременно."""
from __future__ import annotations

from bot.constant.sale import (
    CAT_BODY, CAT_BP_LEVELS, CAT_BP_PREMIUM, CAT_CLAN, CAT_GENIUS, CAT_PATH, CAT_TECHNIQUE,
    SALE_BLACK, SALE_GENIUS, SALE_PASS, SALE_PATHS, SALE_TECHNIQUES,
)

SALE_HOURS = 24

# Скидка, % — вид пятницы → {категория: %}. «Чёрная» — на всё.
SALE_DISCOUNTS: dict[str, dict[str, int]] = {
    SALE_BLACK: {c: 15 for c in (CAT_PATH, CAT_TECHNIQUE, CAT_GENIUS, CAT_BODY, CAT_BP_PREMIUM, CAT_BP_LEVELS, CAT_CLAN)},
    SALE_PATHS: {CAT_PATH: 7},
    SALE_TECHNIQUES: {CAT_TECHNIQUE: 7},
    SALE_GENIUS: {CAT_GENIUS: 7},
    SALE_PASS: {CAT_BP_PREMIUM: 50},
}
SALE_CHOSEN_PERCENT = 10  # «избранные» — на выбранные игроком категории
SALE_CHOSEN_MAX = 3  # сколько категорий можно выбрать
SALE_POWER_PERCENT = 10  # «пятница силы» — пополнение дешевле (коинов больше на 100/(100−10))
SALE_GOLDEN_PERCENT = 5  # «золотая» — +5% коинов к пополнению

# Разовые покупки (одна каждого вида на игрока за пятницу), ₽ = донат-коины.
SALE_REBIRTH_PRICE = 2_000  # смена родословной
SALE_AWAKEN_PRICE = 500  # этап пробуждения
SALE_BLOOD_LEVEL_PRICE = 500  # уровень родословной
