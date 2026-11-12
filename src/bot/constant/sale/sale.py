"""«Пятницы» — скидки и разовые покупки, запускаемые админом (константы)."""
from __future__ import annotations

# Вид пятницы (`sale_events.kind`).
SALE_BLACK = "black"  # скидка на все донаты
SALE_POWER = "power"  # скидка на пополнение
SALE_PATHS = "paths"
SALE_TECHNIQUES = "techniques"
SALE_GENIUS = "genius"
SALE_GOLDEN = "golden"  # бонус к пополнению
SALE_CHOSEN = "chosen"  # скидка на 2–3 категории, которые выбрал игрок
SALE_REBIRTH = "rebirth"  # смена родословной за ₽
SALE_AWAKEN = "awaken"  # этап пробуждения за ₽
SALE_BLOOD_LEVEL = "blood_level"  # уровень родословной за ₽
SALE_PASS = "pass"  # премиум пасса за полцены
SALE_KINDS: tuple[str, ...] = (
    SALE_BLACK, SALE_POWER, SALE_PATHS, SALE_TECHNIQUES, SALE_GENIUS, SALE_GOLDEN, SALE_CHOSEN,
    SALE_REBIRTH, SALE_AWAKEN, SALE_BLOOD_LEVEL, SALE_PASS,
)
SPECIAL_SALES: tuple[str, ...] = (SALE_REBIRTH, SALE_AWAKEN, SALE_BLOOD_LEVEL)  # разовая покупка

# Категории донат-покупок — к ним применяется скидка.
CAT_PATH = "path"
CAT_TECHNIQUE = "technique"
CAT_GENIUS = "genius"
CAT_BODY = "body"
CAT_BP_PREMIUM = "bp_premium"
CAT_BP_LEVELS = "bp_levels"
CAT_CLAN = "clan"
CATEGORIES: tuple[str, ...] = (CAT_PATH, CAT_TECHNIQUE, CAT_GENIUS, CAT_BODY, CAT_BP_PREMIUM, CAT_BP_LEVELS, CAT_CLAN)

LOCK_ACTION_SALE = "sale"

CB_SALE_OPEN = "sale:open"
CB_SALE_PICK_PREFIX = "sale:pick:"  # + категория — «избранные»: выбрать/снять
CB_SALE_BUY_PREFIX = "sale:buy:"  # + вид — разовая покупка
CB_ADMIN_SALE = "adm:sale"
CB_ADMIN_SALE_START_PREFIX = "adm:sale:go:"  # + вид
CB_ADMIN_SALE_STOP = "adm:sale:stop"
AUDIT_SALE_START = "sale_start"
AUDIT_SALE_STOP = "sale_stop"
