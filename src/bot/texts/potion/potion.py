"""Зелья (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.constant.potion import (
    POTION_GUARD,
    POTION_HUNTER,
    POTION_LUCK,
    POTION_POWER,
    POTION_RECRUIT,
    POTION_TRAINING,
    POTION_WEALTH,
)

ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII")

POTION_NAMES: dict[str, str] = {
    POTION_POWER: "⚔️ Зелье силы",
    POTION_GUARD: "🛡 Зелье стойкости",
    POTION_WEALTH: "💰 Зелье богатства",
    POTION_TRAINING: "🏋 Зелье тренировки",
    POTION_RECRUIT: "🎯 Зелье вербовки",
    POTION_LUCK: "🍀 Зелье удачи",
    POTION_HUNTER: "💠 Зелье охотника",
}
POTION_ABOUT: dict[str, str] = {
    POTION_POWER: "Армия бьёт сильнее и крепче держит удар.",
    POTION_GUARD: "Меньше потерь: павшие выживают после боя, часть урона гасится.",
    POTION_WEALTH: "Бизнес приносит больше — считается за то время, пока зелье действует.",
    POTION_TRAINING: "Тренировка статистов успешнее, личная тренировка даёт больше очков развития.",
    POTION_RECRUIT: "Шанс завербовать сразу двоих, на высоких тирах — ранг вербовки выше.",
    POTION_LUCK: "Крутка уников: шанс поднять редкость и крутка без тикета.",
    POTION_HUNTER: "Больше фрагментов с боссов на карте.",
}

POTION_SCREEN = (
    "🧪 <b>Зелья</b>\n━━━━━━━━━━━━━━━━━━\n"
    "💡 Выпил — эффект действует сразу и до конца срока. Один эффект на вид: новое зелье того же "
    "вида заменяет прежнее.\n━━━━━━━━━━━━━━━━━━\n"
    "{medicine}\n━━━━━━━━━━━━━━━━━━\n"
    "{active}"
)
MEDICINE_NONE = (
    "🩺 Без гения медицины доступны тиры I–II. <b>Гений медицины</b> (📈 Развитие → 🧠 Гениальность, "
    "активный) открывает тиры до VII, удешевляет, продлевает и усиливает зелья и даёт авто-зелья."
)
MEDICINE_LINE = "🩺 <b>Гений медицины:</b> тиры до {roman}{extras}"
MEDICINE_EXTRA_DISCOUNT = " · скидка {p}"
MEDICINE_EXTRA_DURATION = " · срок +{p}"
MEDICINE_EXTRA_POWER = " · сила +{p}"
MEDICINE_EXTRA_AUTO = " · авто-зелий: {n}"
ACTIVE_HEAD = "✨ <b>Действуют:</b>\n"
ACTIVE_LINE = "▪️ {name} {roman} — ещё {countdown}{auto}\n"
ACTIVE_NONE = "💤 <i>Сейчас ни одно зелье не действует.</i>"
AUTO_MARK = " 🔁"
BTN_KIND = "{name}"
BTN_KIND_ACTIVE = "{name} · {roman} {countdown}"
BTN_POTIONS = "🧪 Зелья"

KIND_SCREEN = (
    "{name}\n<i>{about}</i>\n━━━━━━━━━━━━━━━━━━\n"
    "⏳ Срок: <b>{minutes}</b> мин.{power}\n━━━━━━━━━━━━━━━━━━\n"
    "{tiers}{state}"
)
KIND_POWER = " Сила эффекта +{p} (гений медицины)."
TIER_LINE = "🧪 <b>{roman}</b> · {price} 🪙 — {effect}\n"
TIER_LINE_LOCKED = "🔒 <b>{roman}</b> — {effect}\n"
KIND_STATE = "\n━━━━━━━━━━━━━━━━━━\n✅ Действует: <b>{roman}</b>, ещё {countdown}."
KIND_AUTO = "\n🔁 Авто-зелье: <b>{roman}</b> — продлевается само, пока хватает NHCoin."
BTN_DRINK = "Выпить {roman} · {price} 🪙"
BTN_AUTO = "🔁 Авто {roman}"
BTN_AUTO_OFF = "⏹ Выключить авто"

# --- popup (без HTML) ---
DRANK_ALERT = "{name} {roman}: действует {minutes} мин"
NOT_ENOUGH_ALERT = "Не хватает NHCoin: нужно {cost}."
LOCKED_ALERT = "Этот тир закрыт: доступны до {roman}. Тиры выше открывает гений медицины."
AUTO_FULL_ALERT = "Все слоты авто-зелий заняты ({slots}). Выключи авто у другого зелья."
AUTO_NO_SLOTS_ALERT = "Авто-зелья открывает гений медицины с 6-го уровня."
AUTO_ON_ALERT = "Авто-зелье включено: {name} {roman}"
AUTO_OFF_ALERT = "Авто-зелье выключено"
BUSY_ALERT = "Обрабатываю…"

PUSH_AUTO_STOPPED = "🧪 Авто-зелье <b>{name} {roman}</b> выключено: {reason}."
AUTO_REASON_COINS = "не хватило NHCoin"
AUTO_REASON_LOCKED = "гений медицины больше не даёт этот тир или слот"
