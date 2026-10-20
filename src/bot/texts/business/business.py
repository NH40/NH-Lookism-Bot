"""Бизнесы на районе — кофе/зал/магазин/нелегальный рынок/парламент, прокачка уровень/вместимость (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML (Telegram не парсит разметку в popup).
"""
from __future__ import annotations

from bot.config.game import (
    BUSINESS_BLACK_MARKET_MAX,
    BUSINESS_BLACK_MARKET_MIN,
    BUSINESS_CAFE_INCOME,
    BUSINESS_GYM_INCOME,
    BUSINESS_GYM_TRAINING_BONUS_PERCENT,
    BUSINESS_MAX_UPGRADE,
    BUSINESS_PARLIAMENT_INCOME,
    BUSINESS_PARLIAMENT_INFLUENCE,
    BUSINESS_SHOP_BASE,
)
from bot.constant.business import BIZ_BLACK_MARKET, BIZ_CAFE, BIZ_GYM, BIZ_PARLIAMENT, BIZ_SHOP

COIN = "🪙"

BUSINESS_NAMES: dict[str, str] = {
    BIZ_CAFE: "☕ Кафе",
    BIZ_SHOP: "🛒 Магазин",
    BIZ_BLACK_MARKET: "🎲 Нелегальный рынок",
    BIZ_GYM: "🏋️ Тренажёрный зал",
    BIZ_PARLIAMENT: "🏛 Парламент",
}

BUSINESS_DESCRIPTIONS: dict[str, str] = {
    BIZ_CAFE: f"стабильно {BUSINESS_CAFE_INCOME}/мин",
    BIZ_SHOP: (
        f"первый — {BUSINESS_SHOP_BASE}/мин, каждый следующий поднимает доход всех магазинов: "
        "3 магазина = 3 кафе, 4 уже больше 4 кафе"
    ),
    BIZ_BLACK_MARKET: f"каждую минуту случайно от {BUSINESS_BLACK_MARKET_MIN} до {BUSINESS_BLACK_MARKET_MAX}",
    BIZ_GYM: f"{BUSINESS_GYM_INCOME}/мин и +{BUSINESS_GYM_TRAINING_BONUS_PERCENT}% к шансам тренировки статистов",
    BIZ_PARLIAMENT: f"{BUSINESS_PARLIAMENT_INCOME:.2g}/мин и +{BUSINESS_PARLIAMENT_INFLUENCE} влияния",
}

OVERVIEW_HEADER = (
    "💼 <b>Бизнес</b>\n━━━━━━━━━━━━━━━━━━\n"
    f"{COIN} NHCoin: <b>{{coins}}</b>\n"
    "💰 Накоплено: <b>{pending}</b>\n"
    "{storage_line}"
    "📈 Доход: ≈{per_minute}/мин · ≈{per_day}/сутки\n"
    "{tax_line}\n━━━━━━━━━━━━━━━━━━\n"
    "🏗 Здания: {buildings}\n"
    "{bonus_line}"
    f"⬆️ Уровень: <b>{{level}}/{BUSINESS_MAX_UPGRADE}</b> (+{{level_bonus}}% к доходу)\n"
    f"📦 Вместимость: <b>{{capacity}}/{BUSINESS_MAX_UPGRADE}</b> ({{slots}} зд. на район)\n━━━━━━━━━━━━━━━━━━\n"
    "{districts_line}"
)
STORAGE_FILLS_IN = "⏳ Хранилище заполнится через <b>{countdown}</b> — <i>забирай хотя бы раз в сутки</i>\n"
STORAGE_FULL = "⚠️ <b>Хранилище заполнено</b> — доход сверх 24 часов сгорает, забери!\n"
NO_BUILDINGS = "<i>пока нет</i>"
BONUS_LINE = "✨ Бонусы зданий: {bonuses}\n"
BONUS_GYM = "+{value}% к шансам тренировки"
BONUS_PARLIAMENT = "+{value} влияния"
DISTRICTS_PICK = "📍 <i>Выбери район, чтобы построить на нём бизнес:</i>"
NO_DISTRICTS = "📭 <i>У тебя пока нет районов — захвати первый на 🗺 Карте, и на нём можно будет построить бизнес.</i>"

BTN_COLLECT = "💰 Забрать {amount}"
BTN_DISTRICT = "📍 Район №{number} — {used}/{capacity}"
BTN_DISTRICT_IN_CITY = "📍 {city} №{number} — {used}/{capacity}"
BTN_UPGRADE_LEVEL = "⬆️ Уровень {next} — {cost} " + COIN
BTN_UPGRADE_CAPACITY = "📦 Вместимость {next} — {cost} " + COIN
BTN_UPGRADE_LEVEL_MAX = "⬆️ Уровень — максимум"
BTN_UPGRADE_CAPACITY_MAX = "📦 Вместимость — максимум"
BTN_BACK_TO_BUSINESS = "◀️ К бизнесу"
BTN_TO_DISTRICT = "📍 К району"
BTN_BUILD = "{name} — {cost} " + COIN
BTN_DISTRICT_BUSINESSES = "💼 Бизнесы района"
BTN_FILL = "🏗 Застроить всё"
BTN_FILL_ALL_DISTRICTS = "🏗 Застроить все районы"
BTN_FILL_TYPE = "{name} — {cost} " + COIN + "/шт"
BTN_DEMOLISH = "🏚 Снести"
BTN_DEMOLISH_ONE = "🏚 {name} ×1"
BTN_DEMOLISH_ALL = "💥 Снести всё на районе"
BTN_DEMOLISH_ALL_CONFIRM = "💥 Да, снести всё"
BTN_DEMOLISH_EVERYWHERE = "🧨 Снести во всех районах"
BTN_DEMOLISH_EVERY_TYPE = "🏚 Все {name} ({count})"
BTN_DEMOLISH_EVERY_ALL = "💥 Вообще всё ({count})"
DEMOLISH_EVERY_SCREEN = (
    "🧨 <b>Снос во всех районах</b>\n"
    "Сносит здания сразу на всех твоих районах. NHCoin <b>не возвращаются</b>, доход до сноса зачислится.\n\n"
    "{buildings}\n\nВыбери, что снести:"
)
DEMOLISH_EVERY_ALL_CONFIRM = "💥 Снести <b>все {count}</b> зданий на всех районах? Это необратимо."
DEMOLISHED_EVERYWHERE = "Снесено зданий во всех районах: {count}"
BTN_CANCEL = "◀️ Отмена"
FILL_SCREEN = (
    "🏗 <b>Застроить всё</b> — {scope}\n━━━━━━━━━━━━━━━━━━\n"
    "📦 Свободных мест: <b>{free}</b>\n"
    f"{COIN} У тебя: <b>{{coins}}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Выбери здание — построю его на каждом свободном месте, пока хватит NHCoin.</i>"
)
FILL_SCOPE_ALL = "все районы"
FILL_SCOPE_DISTRICT = "район №{number}"
DEMOLISH_SCREEN = (
    "🏚 <b>Снос — район №{number}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🏗 Здания: {buildings}\n━━━━━━━━━━━━━━━━━━\n"
    "<i>NHCoin за снос не возвращаются — место освобождается под другую постройку.</i>"
)
DEMOLISH_ALL_CONFIRM = (
    "💥 <b>Снести ВСЕ здания на районе №{number}?</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🏗 {buildings}\n<i>NHCoin не вернутся. Действие необратимо.</i>"
)

DISTRICT_SCREEN = (
    "📍 <b>Район №{number}</b> — бизнесы\n━━━━━━━━━━━━━━━━━━\n"
    "📦 Места: <b>{used}/{capacity}</b>\n"
    "🏗 Здания: {buildings}\n"
    f"{COIN} У тебя: <b>{{coins}}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "{build_block}"
)
BUILD_HEADER = "🏗 <b>Что построить:</b>\n"
BUILD_LINE = "{name} — {cost} " + COIN + ": {description}"
NO_FREE_SLOTS_BLOCK = "🚫 <i>Мест на районе нет — прокачай 📦 Вместимость на экране бизнеса.</i>"

# --- popup (без HTML) ---
COLLECTED = "Забрано: {amount} NHCoin"
NOTHING_TO_COLLECT = "Пока нечего забирать — доход копится каждую минуту."
BUILT = "Построено: {name} на районе №{number} (−{cost} NHCoin)"
UPGRADED_LEVEL = "Уровень бизнеса повышен до {level} (−{cost} NHCoin)"
UPGRADED_CAPACITY = "Вместимость повышена до {level} (−{cost} NHCoin)"
# Жалоба 2026-10-13: «накопленные коины после прокачки исчезают» — они зачисляются в кошелёк.
UPGRADE_COLLECTED = ". Накопленные {amount} NHCoin зачислены в кошелёк"
NOT_ENOUGH_COINS = "Не хватает NHCoin: нужно {cost}, у тебя {balance}."
NO_FREE_SLOT = "На этом районе нет свободных мест — прокачай вместимость."
NOT_DISTRICT_OWNER = "Этот район уже не твой."
MAX_UPGRADE = "Уже максимальный уровень."
BUSY = "Обрабатываю…"
BUILT_ALL = "Построено: {name} ×{count} на {districts} р-нах (−{cost} NHCoin)"
DEMOLISHED = "Снесено зданий: {count} на районе №{number}"
NOTHING_TO_DEMOLISH = "Сносить нечего — таких зданий на районе нет."
NO_FREE_SLOTS_ANYWHERE = "Свободных мест нет — прокачай вместимость."


def buildings_summary(counts: dict[str, int]) -> str:
    """«☕ Кафе ×2 · 🛒 Магазин ×1» — в порядке `BUSINESS_NAMES`, только построенные."""
    parts = [f"{name} ×{counts[type_]}" for type_, name in BUSINESS_NAMES.items() if counts.get(type_)]
    return " · ".join(parts) if parts else NO_BUILDINGS
