"""Ивенты императора (тексты). Popup-алерты — БЕЗ HTML."""
from __future__ import annotations

from bot.constant.empire import (
    EVENT_COINS,
    EVENT_DAILY,
    EVENT_DRILL,
    EVENT_FEAST,
    EVENT_HOLIDAY,
    EVENT_STATISTS,
    EVENT_TOURNAMENT,
)

BTN_EVENTS = "🎉 Ивенты империи"
BTN_BACK_TO_EVENTS = "◀️ К ивентам"
BTN_HOURS = "{hours} ч"
BTN_START = "✅ Запустить"
BTN_CLAIM = "🎁 Забрать: {title}"
BTN_OPEN_SUBJECT = "🎉 Открыть ивенты"

TITLES: dict[str, str] = {
    EVENT_COINS: "💰 Раздача NHCoin",
    EVENT_STATISTS: "🧍 Раздача статистов",
    EVENT_FEAST: "🎉 Праздник",
    EVENT_HOLIDAY: "🕊 Налоговые каникулы",
    EVENT_DRILL: "🏋️ Военные сборы",
    EVENT_TOURNAMENT: "🏆 Турнир империи",
    EVENT_DAILY: "🎁 Ежедневный подарок",
}
ABOUT: dict[str, str] = {
    EVENT_COINS: "Фонд на N мест: каждый подданный один раз забирает сумму. Длится {claim_hours} ч, остаток вернётся тебе.",
    EVENT_STATISTS: "Ты оплачиваешь статистов ранга (цена — {per_power} 🪙 за 1 мощи статиста), каждый подданный один раз забирает свою часть в лагерь защиты. Длится {claim_hours} ч, остаток вернётся деньгами.",
    EVENT_FEAST: "Подданные получают +{feast}% к доходу бизнеса. Бонус платится из твоего фонда, пока он не кончится; остаток вернётся.",
    EVENT_HOLIDAY: "Налог 0% для всех подданных. Бесплатно: ты просто не получаешь налог (пассивные +10% остаются).",
    EVENT_DRILL: "−{drill}% к КД личной тренировки и тренировки статистов подданных. Цена — за каждого подданного, заходившего за сутки, в час; монеты сгорают.",
    EVENT_TOURNAMENT: "{tour_hours} ч: трое подданных с наибольшим числом побед в боях с игроками делят фонд 50/30/20%. Нет победителей — фонд вернётся.",
    EVENT_DAILY: "Каждый день подданный забирает сумму. Фонд = сумма × дни × подданные сейчас, остаток вернётся. До {max_days} дней.",
}
PROMPTS: dict[str, str] = {
    EVENT_COINS: "💰 Напиши: <b>сумма_на_игрока мест</b>\nНапример: <code>50000 20</code>",
    EVENT_STATISTS: "🧍 Напиши: <b>РАНГ штук_на_игрока мест</b>\nНапример: <code>B+ 100 20</code>",
    EVENT_FEAST: "🎉 Праздник на {hours} ч. Напиши фонд в NHCoin (минимум {min_fund}).",
    EVENT_TOURNAMENT: "🏆 Напиши призовой фонд в NHCoin (минимум {min_fund}).",
    EVENT_DAILY: "🎁 Напиши: <b>монет_в_день дней</b> (дней 1–{max_days})\nНапример: <code>10000 3</code>",
}

EVENTS_SCREEN = "🎉 <b>Ивенты империи</b>\n━━━━━━━━━━━━━━━━━━\n👥 Подданных: <b>{subjects}</b> (за сутки заходили {active})\n\n{lines}"
KIND_LINE_ACTIVE = "{title} — <b>идёт</b>, ещё {left}"
KIND_LINE_CD = "{title} — перезарядка {left}"
KIND_LINE_READY = "{title} — можно запустить"
KIND_SCREEN = "{title}\n━━━━━━━━━━━━━━━━━━\n{about}\n\n{status}"
STATUS_ACTIVE = "⏳ Идёт, осталось {left}. Забрали: {claims}. Фонд: {pool} 🪙{units}"
STATUS_UNITS = ", статистов: {units}"
STATUS_CD = "⏱ Перезарядка: {left}"
STATUS_READY = "Выбери параметры:"
DRILL_CONFIRM = "🏋️ Сборы на {hours} ч. Цена: <b>{price}</b> 🪙 (подданных за сутки: {active})."
HOLIDAY_CONFIRM = "🕊 Налоговые каникулы на {hours} ч. Налог с подданных не придёт."
STARTED = "✅ {title} запущен. Списано: {cost} 🪙. Подданным разосланы уведомления."

PUSH_STARTED = "👑 <b>{emperor}</b> устроил ивент: {title}\n{details}"
DETAILS: dict[str, str] = {
    EVENT_COINS: "Забери {per} 🪙 — мест: {slots}, успей за {hours} ч.",
    EVENT_STATISTS: "Забери {per} статистов ранга {rank} — мест: {slots}, успей за {hours} ч.",
    EVENT_FEAST: "{hours} ч: +{percent}% к доходу бизнеса.",
    EVENT_HOLIDAY: "{hours} ч: налог 0%.",
    EVENT_DRILL: "{hours} ч: −{percent}% к КД тренировок.",
    EVENT_TOURNAMENT: "{hours} ч: побеждай в боях с игроками — тройка лучших делит {prize} 🪙.",
    EVENT_DAILY: "{days} дн.: каждый день забирай {per} 🪙.",
}
PUSH_FINISHED = "🎉 Ивент «{title}» завершён. Роздано: {spent} 🪙, забрали: {claims}, возвращено: {refund} 🪙."
PUSH_PRIZE = "🏆 Турнир империи: {place} место, {wins} побед — приз {prize} 🪙!"
TOURNAMENT_WINNERS = "\nПобедители: {winners}"

SUBJECT_SCREEN = "🎉 <b>Ивенты твоей империи</b>\n━━━━━━━━━━━━━━━━━━\n{lines}"
SUBJECT_LINE = "{title} — ещё {left}\n   {details}"
SUBJECT_NONE = "Сейчас император ничего не устроил."
SUBJECT_NO_EMPEROR = "У твоего города нет императора."

# --- popup (без HTML) ---
NOT_EMPEROR_ALERT = "Ивенты запускает только император."
ACTIVE_ALERT = "Такой ивент уже идёт."
COOLDOWN_ALERT = "Перезарядка: ещё {left}."
NOT_ENOUGH_ALERT = "Не хватает NHCoin: нужно {cost}."
BAD_INPUT = "Не понял. {prompt}"
NO_SUBJECTS_ALERT = "В твоей империи нет подданных."
CLAIMED_COINS = "Получено {amount} NHCoin."
CLAIMED_UNITS = "Получено {amount} статистов ранга {rank} (лагерь защиты)."
GONE_ALERT = "Ивент уже закончился или не твоей империи."
ALREADY_ALERT = "Ты уже забрал."
EMPTY_ALERT = "Фонд уже разобрали."
BUSY = "Обрабатываю…"
