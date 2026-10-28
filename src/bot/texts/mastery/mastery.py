"""Мастерство — экран цепочки «Преодоление стены», бой с Томом Ли (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML.
"""
from __future__ import annotations

from bot.constant.mastery import TASK_EQUAL_WIN, TASK_EXTRAS, TASK_PVP_WINS, TASK_TOM, TASK_TRAININGS

STAGE_NAMES: dict[int, str] = {1: "Стена", 2: "Трансцендентность", 3: "Мастерство"}

MASTERY_SCREEN = "🥋 <b>Мастерство</b>\n━━━━━━━━━━━━━━━━━━\n{tiers}\n━━━━━━━━━━━━━━━━━━\n{quest_block}"
TIER_LINE = "{label}: {tier}"

QUEST_LOCKED = "🔒 Задание «Преодоление стены» откроется, когда все характеристики дойдут до CX."
QUEST_PENDING = "🧱 Задание этапа {stage} — {stage_name} придёт в случайный момент. Когда именно — не знает никто: чем выше потенциал, тем дольше ждать."
QUEST_ACTIVE = "🧱 <b>Этап {stage} — {stage_name}</b>\n\n{tasks}"
QUEST_TRAINER = (
    "✅ <b>Том Ли побеждён!</b> Тренер Том Ли ждёт в 🛍 Магазине.\n"
    "Очко мастерства — {price} 🪙 · куплено {bought}/4 · невложенных: {free}\n"
    "Очко вкладывается в любое мастерство, но не выше ступени «{stage_name}»."
)
QUEST_COMPLETE = "🏆 <b>Мастерство постигнуто</b> — все три этапа пройдены."
QUEST_BREAKTHROUGH = (
    "🧱 <b>Стена перед этапом {stage} — {stage_name}</b>\n"
    "Чтобы её пробить, нужно сделать что-то грандиозное — любые {need} из списка:\n{items}\n\n"
    "Как только пробьёшь, задание этапа придёт в случайный момент."
)
BREAKTHROUGH_DONE = "✅ {label}"
BREAKTHROUGH_TODO = "⬜ {label}"
BREAKTHROUGH_LABELS: dict[str, str] = {
    "path": "Пробудить путь",
    "tech10": "Докачать любую уникальную технику до 10 уровня",
    "awaken": "Пройти этап пробуждения",
    "phase": "Стать кругом или императором",
}
FREE_POINTS_LINE = "\n\n🎯 Невложенных очков мастерства: <b>{free}</b>"

TASK_LABELS: dict[str, str] = {
    TASK_TRAININGS: "Провести личные тренировки",
    TASK_EXTRAS: "Провести тренировки статистов",
    TASK_PVP_WINS: "Победить в PvP-вызовах (нападающим)",
    TASK_EQUAL_WIN: "Победить игрока с мощью ±10% от своей",
    TASK_TOM: "Победить Тома Ли",
}
TASK_DONE = "✅ {label}"
TASK_PROGRESS = "⬜ {label}: {progress}/{target}"
TASK_TODO = "⬜ {label}"
TASK_LOCKED = "🔒 {label} — после остальных заданий"
TOM_HINT = "\n\n👊 Том Ли: мощь {power}. Против него не работают блок и побег — бьётся лагерь атаки."

BTN_FIGHT_TOM = "⚔️ Сразиться с Томом Ли"
BTN_INVEST = "+ {label}"
BTN_SHOP = "🛍 Магазин"

TOM_RESULT = (
    "🥊 <b>Бой с Томом Ли</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{headline}\n"
    "🔁 Раундов: <b>{rounds}</b>\n"
    "⚔️ Твоя атака: мощь {power}, погибло {dead}\n"
    "👊 Том Ли: мощь {tom_power}, осталось {tom_left}"
)
TOM_WON = "✅ <b>Победа!</b> Тренер Том Ли теперь ждёт тебя в 🛍 Магазине."
TOM_LOST = "❌ <b>Поражение.</b> Том оказался сильнее — усиль лагерь атаки и попробуй снова после КД."

PUSH_QUEST = (
    "🧱 <b>Новое задание: «Преодоление стены»</b>\n"
    "Этап {stage} — {stage_name}. Открой 🥋 Мастерство, чтобы посмотреть задания."
)
BTN_OPEN_MASTERY = "🥋 Мастерство"

# --- popup (без HTML) ---
QUEST_NOT_ACTIVE_ALERT = "Сейчас нет активного задания «Преодоление стены»."
TOM_LOCKED_ALERT = "Том Ли откроется после остальных заданий этапа."
NO_FREE_POINTS_ALERT = "Нет невложенных очков мастерства — купи их у тренера Тома Ли в магазине."
MASTERY_CAPPED_ALERT = "Это мастерство уже на ступени текущего этапа — вложи очко в другое."
INVESTED_ALERT = "{label}: {tier}"
STAGE_FINISHED_ALERT = "{label}: {tier}. Этап пройден! Перед следующим — стена: сделай что-то грандиозное (список в Мастерстве)."
CHAIN_COMPLETE_ALERT = "{label}: {tier}. Мастерство постигнуто!"
