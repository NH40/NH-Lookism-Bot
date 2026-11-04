"""Ультра инстинкт — экран настроек (тексты)."""
from __future__ import annotations

from bot.constant.ultra_instinct import ACTION_EXTRAS, ACTION_RECRUIT, ACTION_ROLL, ACTION_SCHOOL, ACTION_TRAIN

ULTRA_SCREEN = (
    "⚡ <b>Ультра инстинкт</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Выбери, что делается само, пока тебя нет в боте.\n"
    "{boss_block}"
)
BOSS_BLOCK = (
    "\n\n👹 <b>Автобой с боссами.</b> Бой идёт, только если прогноз обещает победу "
    "и ожидаемые потери не выше потолка: <b>{max_loss}%</b>."
)
BOSS_LOCKED = "\n\n👹 Автобой с боссами открывается на 10 уровне родословной."

ACTION_LABELS = {
    ACTION_RECRUIT: "🎯 Вербовка",
    ACTION_TRAIN: "🏋️ Личная тренировка",
    ACTION_EXTRAS: "💪 Тренировка статистов",
    ACTION_SCHOOL: "🎓 Занятия у учителей",
    ACTION_ROLL: "🎫 Крутка тикетов",
}
MARK_ON = "✅"
MARK_OFF = "⬜️"
BTN_ACTION = "{mark} {label}"
BTN_BOSS = "{mark} {name}"
BTN_LOSS = "{mark}{percent}%"
BTN_OPEN_ULTRA = "⚡ Ультра инстинкт"
NOT_AVAILABLE_ALERT = "Это откроется на следующих уровнях родословной Ямадзаки."
