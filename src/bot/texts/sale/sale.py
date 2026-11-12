"""«Пятницы» (тексты). Popup-алерты — БЕЗ HTML."""
from __future__ import annotations

from bot.config.sale import (
    SALE_AWAKEN_PRICE, SALE_BLOOD_LEVEL_PRICE, SALE_CHOSEN_MAX, SALE_CHOSEN_PERCENT, SALE_GOLDEN_PERCENT, SALE_POWER_PERCENT,
    SALE_REBIRTH_PRICE,
)
from bot.constant.sale import (
    CAT_BODY, CAT_BP_LEVELS, CAT_BP_PREMIUM, CAT_CLAN, CAT_GENIUS, CAT_PATH, CAT_TECHNIQUE,
    SALE_AWAKEN, SALE_BLACK, SALE_BLOOD_LEVEL, SALE_CHOSEN, SALE_GENIUS, SALE_GOLDEN, SALE_PASS, SALE_PATHS, SALE_POWER,
    SALE_REBIRTH, SALE_TECHNIQUES,
)

TITLES: dict[str, str] = {
    SALE_BLACK: "🖤 Чёрная пятница",
    SALE_POWER: "💪 Пятница силы",
    SALE_PATHS: "🛤 Пятница путей",
    SALE_TECHNIQUES: "🥋 Пятница техник",
    SALE_GENIUS: "🧠 Пятница гениев",
    SALE_GOLDEN: "🥇 Золотая пятница",
    SALE_CHOSEN: "⭐ Пятница избранных",
    SALE_REBIRTH: "🔄 Пятница перерождения",
    SALE_AWAKEN: "🌅 Пятница пробуждения",
    SALE_BLOOD_LEVEL: "🩸 Пятница родословной",
    SALE_PASS: "🎫 Пятница пропуска",
}
ABOUT: dict[str, str] = {
    SALE_BLACK: "Скидка 15% на все донаты.",
    SALE_POWER: f"Пополнение дешевле на {SALE_POWER_PERCENT}%: за те же рубли больше коинов.",
    SALE_PATHS: "Скидка 7% на пути.",
    SALE_TECHNIQUES: "Скидка 7% на техники.",
    SALE_GENIUS: "Скидка 7% на гениальности.",
    SALE_GOLDEN: f"+{SALE_GOLDEN_PERCENT}% коинов к каждому пополнению.",
    SALE_CHOSEN: f"Скидка {SALE_CHOSEN_PERCENT}% на донаты, которые ты выберешь сам (до {SALE_CHOSEN_MAX}).",
    SALE_REBIRTH: f"Смена родословной за {SALE_REBIRTH_PRICE} 💎 (одна за пятницу).",
    SALE_AWAKEN: f"+1 этап пробуждения без сброса за {SALE_AWAKEN_PRICE} 💎 (один за пятницу).",
    SALE_BLOOD_LEVEL: f"+1 уровень родословной за {SALE_BLOOD_LEVEL_PRICE} 💎 (один за пятницу).",
    SALE_PASS: "Премиум пасса за полцены.",
}
CATEGORY_NAMES: dict[str, str] = {
    CAT_PATH: "Пути", CAT_TECHNIQUE: "Техники", CAT_GENIUS: "Гениальности", CAT_BODY: "Второе тело",
    CAT_BP_PREMIUM: "Премиум пасса", CAT_BP_LEVELS: "Уровни пасса", CAT_CLAN: "Уровень клана",
}

BANNER = "\n\n{title} — ещё {left}\n{about}"
SCREEN = "{title}\n━━━━━━━━━━━━━━━━━━\n{about}\n⏳ Осталось: {left}"
CHOSEN_HINT = "\n\nВыбрано {n}/{max}: {list}"
BOUGHT_LINE = "\n\n✅ Ты уже воспользовался этой пятницей."
PUSH_START = "🛍 <b>{title}</b> — 24 часа!\n{about}\nОткрой ⚙️ Настройки → 💎 Донат."

BTN_SALE = "🛍 {title}"
BTN_PICK = "{mark} {name}"
BTN_BUY = "Купить — {price} 💎"
BTN_BACK = "◀️ К донату"

NONE_ALERT = "Сейчас пятницы нет."
TOO_MANY_ALERT = f"Можно выбрать не больше {SALE_CHOSEN_MAX}."
BOUGHT_ALERT = "Готово! {title}: покупка сделана."
ALREADY_ALERT = "Уже куплено в эту пятницу."
CANNOT_ALERT = "Эта покупка тебе сейчас недоступна (нет родословной, уже максимум или смена уже есть)."
NOT_ENOUGH_ALERT = "Не хватает донат-коинов: нужно {price}, у тебя {balance}."
BUSY_ALERT = "Обрабатываю…"
REBIRTH_DONE = " Смени родословную в профиле → 🩸 Родословная."

ADMIN_SCREEN = "🛍 <b>Пятницы</b>\n━━━━━━━━━━━━━━━━━━\n{status}\n\nОдна за раз, сама заканчивается через 24 ч. Игрокам приходит уведомление."
ADMIN_ACTIVE = "Идёт: <b>{title}</b>, ещё {left}."
ADMIN_NONE = "Сейчас ничего не идёт. Выбери, что запустить:"
ADMIN_BTN_STOP = "⏹ Выключить"
ADMIN_STARTED = "Запущено: {title}. Рассылаю уведомление."
ADMIN_ACTIVE_ALERT = "Уже идёт другая пятница — сначала выключи её."
ADMIN_STOPPED = "Пятница выключена."
