"""Гениальность (тексты). Popup-алерты — без HTML. Эффекты уровней описываются из данных
(`texts/development/effects.py`)."""
from __future__ import annotations

from bot.config.genius import GENIUS_ROLL_COINS, GENIUS_ROLL_FRAGMENTS
from bot.constant.genius import (
    GENIUS_BUSINESS,
    GENIUS_CHARISMA,
    GENIUS_HACKING,
    GENIUS_MEDIA,
    GENIUS_MEDICINE,
    GENIUS_OBSERVATION,
    GENIUS_TACTICS,
    GENIUS_TRAINING,
    GENIUS_WAR,
    GENIUS_WEAPONS,
)

GENIUS_NAMES: dict[str, str] = {
    GENIUS_BUSINESS: "Гений бизнеса",
    GENIUS_WAR: "Гений войны",
    GENIUS_TRAINING: "Гений тренировок",
    GENIUS_WEAPONS: "Гений оружия",
    GENIUS_MEDIA: "Гений медиа",
    GENIUS_HACKING: "Гений хакинга",
    GENIUS_OBSERVATION: "Гений наблюдения",
    GENIUS_MEDICINE: "Гений медицины",
    GENIUS_TACTICS: "Гений тактики",
    GENIUS_CHARISMA: "Гений харизмы",
}
GENIUS_THEMES: dict[str, str] = {
    GENIUS_BUSINESS: "Деньги: доход, дешёвые постройки, большое хранилище, меньше налога императору.",
    GENIUS_WAR: "Военное дело: атака, частые бои, вербовка сильнее, удар до боя.",
    GENIUS_TRAINING: "Тренировки: больше очков развития, дешёвые ранги, успешнее статисты.",
    GENIUS_WEAPONS: "Оружие: усиливает уникальную технику, криты и пробитие.",
    GENIUS_MEDIA: "Известность: доход, вербовка двоих, быстрее тикеты.",
    GENIUS_HACKING: "Взлом: разведка цели вплоть до её билда, саботаж сильнее и тише.",
    GENIUS_OBSERVATION: "Наблюдение: журналы действий игроков, метки, предвидение.",
    GENIUS_MEDICINE: "Медицина: павшие встают в строй, меньше потерь.",
    GENIUS_TACTICS: "Тактика: сильное начало боя, рывок, подавление реакций врага.",
    GENIUS_CHARISMA: "Харизма: вербовка и уники — двое за раз, редкие чаще, бесплатные крутки.",
}

GENIUS_LINE = "🧠 <b>Гениальность:</b> {name} · ур. {level}"
GENIUS_LINE_NONE = "🧠 <b>Гениальность:</b> —"

GENIUS_SCREEN = (
    "🧠 <b>Гениальность</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚡ Активна: <b>{active}</b>\n"
    "🧩 Фрагменты гениальности: <b>{fragments}</b> (падают с босса Элиты на 🗺 Карте)\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "📚 <b>Твои гениальности:</b>\n{owned}\n\n"
    "<i>Активна одна — переключай под задачу. Новую — прокрутом за "
    f"{GENIUS_ROLL_FRAGMENTS} 🧩 и {GENIUS_ROLL_COINS:,} 🪙 (выпала имеющаяся — прокрут сгорает).</i>"
)
OWNED_LINE = "{mark} {name} · ур. {level}"
MARK_ACTIVE = "✅"
MARK_OWNED = "▫️"

GENIUS_DETAIL = (
    "🧠 <b>{name}</b> · ур. <b>{level}/10</b>{active}\n"
    "<i>{theme}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{levels}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{next_line}"
)
DETAIL_ACTIVE = " · ✅ активна"
LEVEL_LINE_DONE = "✅ {n}. {effect}"
LEVEL_LINE_LOCKED = "🔒 {n}. {effect}"
NEXT_LEVEL_LINE = "⬆️ Следующий уровень — <b>{cost}</b> 🧩 (у тебя {have})."
MAX_LEVEL_LINE = "🏆 <b>Максимальный уровень.</b>"

BTN_GENIUS = "🧠 Гениальность"
BTN_GENIUS_ITEM = "{mark} {name} · {level}"
BTN_LEVEL_UP = "⬆️ Улучшить · {cost} 🧩"
BTN_ACTIVATE = "✅ Сделать активной"
BTN_ROLL = f"🎲 Прокрут · {GENIUS_ROLL_FRAGMENTS} 🧩 + {GENIUS_ROLL_COINS:,} 🪙"
BTN_BACK_TO_GENIUS = "◀️ К гениальностям"

ROLL_NEW = "🎲 Новая гениальность: <b>{name}</b>!"
ROLL_DUPLICATE = "🎲 Выпал <b>{name}</b> — он у тебя уже есть, прокрут сгорел."
ACTIVATED_ALERT = "Активна: {name}"
LEVEL_UP_ALERT = "{name}: уровень {level}"
NOT_ENOUGH_ALERT = "Не хватает: нужно {cost} фрагментов, у тебя {have}."
NOT_ENOUGH_ROLL_ALERT = f"Нужно {GENIUS_ROLL_FRAGMENTS} фрагментов и {GENIUS_ROLL_COINS:,} NHCoin."
MAX_LEVEL_ALERT = "Уже максимальный уровень."
SWAP_COOLDOWN_ALERT = "Переключать гениальность можно раз в 15 минут — ещё {countdown}."
NOT_OWNED_ALERT = "Этой гениальности у тебя нет."
BUSY_ALERT = "Обрабатываю…"
FIRST_GENIUS = "🧠 В тебе проснулся <b>{name}</b> — твоя первая гениальность. Подробнее — в 📈 Развитии."
