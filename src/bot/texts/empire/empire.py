"""Император — экран «👑 Империя», налоги (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML (Telegram не парсит разметку в popup).
"""
from __future__ import annotations

from bot.config.empire import (
    EMPEROR_PASSIVE_BONUS_PERCENT,
    EMPIRE_TAX_MAX_PERCENT,
    EMPIRE_TAX_MIN_PERCENT,
    EMPIRE_WAR_TREASURY_MAX_PERCENT,
    EMPIRE_WAR_TREASURY_MIN_PERCENT,
    SABOTAGE_CHANCE_PERCENT,
    SABOTAGE_RECENT_HOURS,
    SABOTAGE_STATISTS_PERCENT,
    SABOTAGE_TREASURY_CAP,
    SABOTAGE_TREASURY_PERCENT,
)
from bot.constant.empire import SABOTAGE_STATISTS, SABOTAGE_TREASURY, SABOTAGE_UNIQUE

BTN_EMPIRE = "👑 Империя"
BTN_RATE = "{percent}%"
BTN_RATE_CURRENT = "• {percent}% •"
BTN_PERSONAL = "🎯 Персональная ставка"
BTN_RESET_PERSONAL = "↩️ Как у всех"
BTN_BACK_TO_EMPIRE = "◀️ К империи"

EMPIRE_SCREEN = (
    "👑 <b>Империя</b>\n━━━━━━━━━━━━━━━━━━\n"
    "🏙 Городов: <b>{cities}</b>\n"
    "👥 Игроков платят налог: <b>{players}</b>\n"
    "🪙 Казна (твой кошелёк NHCoin): <b>{coins}</b>\n"
    "💰 Собрано с империи всего: <b>{collected}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "📜 <b>Общий налог: {rate}%</b>\n"
    f"Налог игрок теряет — он уходит тебе. Сверху ты пассивно получаешь +{EMPEROR_PASSIVE_BONUS_PERCENT}% "
    "от дохода каждого игрока <i>(у него не вычитается)</i>.\n"
    "{overrides_block}"
    "{incoming_line}"
    "{sabotage_line}"
)
OVERRIDES_HEADER = "\n━━━━━━━━━━━━━━━━━━\n🎯 <b>Персональные ставки</b> ({total}):\n"
OVERRIDE_LINE = "👤 {name} — <b>{percent}%</b>\n"
OVERRIDES_MORE = "<i>…и ещё {more}</i>\n"

PERSONAL_PROMPT = (
    "🎯 Пришли юзернейм игрока твоей империи (например, <code>@nickname</code>) — "
    f"назначу ему отдельную ставку {EMPIRE_TAX_MIN_PERCENT}–{EMPIRE_TAX_MAX_PERCENT}%."
)
SUBJECT_NOT_FOUND = "Такого игрока нет в твоих городах (или у него не указан юзернейм). Пришли другой юзернейм:"
PERSONAL_PICK = "🎯 <b>Ставка для {name}</b>\n━━━━━━━━━━━━━━━━━━\nСейчас — <b>{percent}%</b>{note}"
PERSONAL_NOTE_GLOBAL = " (общая)"
PERSONAL_NOTE_OWN = " (персональная)"

RATE_SET_ALERT = "Общий налог: {percent}%"
PERSONAL_SET_ALERT = "Ставка игрока: {percent}%"
PERSONAL_RESET_ALERT = "Игрок платит общий налог"
NOT_EMPEROR_ALERT = "Ты не император."
SUBJECT_GONE_ALERT = "Игрок уже не в твоей империи."
INVALID_RATE_ALERT = f"Ставка — от {EMPIRE_TAX_MIN_PERCENT} до {EMPIRE_TAX_MAX_PERCENT}%."

# Строка на экране бизнеса у игрока, который платит налог.
TAX_LINE = "👑 Налог императору <b>{emperor}</b>: <b>{percent}%</b> <i>(уже вычтен)</i>\n"

SABOTAGE_LINE = (
    f"\n🕵️ Диверсий за {SABOTAGE_RECENT_HOURS} ч: <b>{{total}}</b> (удачных: {{success}}). "
    "Кто это был — не узнать (пока у шпионов нет навыка раскрытия).\n"
)

# --- саботаж (экран игрока) ---
BTN_SABOTAGE = "🕵️ Саботаж"
SABOTAGE_LABELS: dict[str, str] = {
    SABOTAGE_STATISTS: "👥 Украсть статистов",
    SABOTAGE_UNIQUE: "🃏 Переманить уника",
    SABOTAGE_TREASURY: "🪙 Украсть из казны",
}
BTN_SABOTAGE_ACTION = "{label} · {chance}%"
BTN_SABOTAGE_COOLDOWN = "{label} · ⏳ {countdown}"
SABOTAGE_SCREEN = (
    "🕵️ <b>Саботаж</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Император твоего города — <b>{emperor}</b>, он берёт с тебя налог {percent}%. "
    "Отбей своё: император не узнает, кто это был.\n━━━━━━━━━━━━━━━━━━\n"
    f"👥 Статисты — {SABOTAGE_STATISTS_PERCENT}% одной его стопки (не больше, чем у тебя своих).\n"
    "🃏 Уник — одна копия, не стоящая на позиции.\n"
    f"🪙 Казна — {SABOTAGE_TREASURY_PERCENT}% его NHCoin, до {SABOTAGE_TREASURY_CAP:,} за раз.\n\n"
    "━━━━━━━━━━━━━━━━━━\n<i>Шанс у каждого действия фиксированный. После попытки — перерыв у этого действия, остальные доступны.</i>\n"
    "{cooldown_line}"
)
SABOTAGE_READY_LINE = "Выбирай:"
NO_EMPEROR = "У твоего города нет императора — саботировать некого."
NOT_MARKED_ALERT = "Саботировать можно только помеченного игрока — это способность пути Сенсорики."
NOTHING_TO_STEAL_ALERT = "У императора нечего украсть этим способом."
SABOTAGE_COOLDOWN_ALERT = "Следующая попытка через {countdown}."

SABOTAGE_SUCCESS = {
    SABOTAGE_STATISTS: "✅ Удалось! Ты увёл <b>{amount}</b> статистов ранга {rank} — они в твоём лагере атаки.",
    SABOTAGE_UNIQUE: "✅ Удалось! <b>{card}</b> переманен к тебе — он в твоём лагере атаки.",
    SABOTAGE_TREASURY: "✅ Удалось! Из казны унесено <b>{amount}</b> NHCoin.",
}
SABOTAGE_FAIL = "❌ Не вышло — охрана императора начеку. Император не знает, что это был ты."

# Пуши императору — анонимные.
PUSH_SABOTAGE_SUCCESS = {
    SABOTAGE_STATISTS: "🕵️ Диверсия! Неизвестный увёл {amount} твоих статистов ранга {rank}.",
    SABOTAGE_UNIQUE: "🕵️ Диверсия! Неизвестный переманил твоего уника {card}.",
    SABOTAGE_TREASURY: "🕵️ Диверсия! Из казны украдено {amount} NHCoin.",
}
PUSH_SABOTAGE_FAIL = "🛡 Кто-то пытался устроить диверсию против тебя, но охрана помешала."

# Справка для экрана: шансы — из конфига, не дублируются в тексте вручную.
SABOTAGE_CHANCES = SABOTAGE_CHANCE_PERCENT

# --- Война императоров ---
BTN_WAR = "⚔️ Война императоров"
BTN_WAR_TARGET = "{name} · {country} · 🏙 {cities}"
BTN_WAR_DECLARE = "⚔️ Объявить войну"
BTN_WAR_ACCEPT = "⚔️ Принять бой"
BTN_BACK_TO_TARGETS = "◀️ К списку"
BTN_PREV = "◀️"
BTN_NEXT = "▶️"
WAR_TARGETS_SCREEN = (
    "⚔️ <b>Война императоров</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Выбери императора. Принял вызов — бой лагерей атаки; не принял вовремя — автобой против его лагеря защиты.\n"
    f"Победитель забирает {EMPIRE_WAR_TREASURY_MIN_PERCENT}–{EMPIRE_WAR_TREASURY_MAX_PERCENT}% казны "
    "проигравшего (чем ближе силы, тем больше), а победивший нападающий — ещё и случайные города: "
    "чем больше перевес, тем больше. Император без городов возвращается в банду."
)
NO_WAR_TARGETS = "\n\nДругих императоров пока нет."
WAR_TARGET_SCREEN = (
    "⚔️ Император <b>{name}</b> ({country})\n━━━━━━━━━━━━━━━━━━\n"
    "🏙 Городов: <b>{cities}</b>\n"
    "🪙 Казна: <b>{coins}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Окно принятия — {window}, после объявления у тебя перерыв {cooldown}.</i>"
)
WAR_DECLARED = "⚔️ Вызов отправлен императору {defender}. Не примет за {window} — бой пройдёт против его лагеря защиты."
PUSH_WAR_DECLARED = (
    "⚔️ Император <b>{attacker}</b> объявил тебе войну!\n"
    "Примешь — бой лагерей атаки. Не примешь за {window} — бой пройдёт против твоего лагеря защиты."
)
INCOMING_WAR_LINE = "\n⚔️ <b>Против тебя война</b>: {attacker} — принять в течение {countdown}.\n"

# Алерты — без HTML.
WAR_NOT_EMPEROR_ALERT = "Воевать могут только императоры."
TARGET_NOT_EMPEROR_ALERT = "Этот игрок уже не император."
TARGET_NO_CITIES_ALERT = "У этого императора не осталось городов."
TARGET_SHIELDED_ALERT = "Этот император недавно воевал — на него нельзя напасть ещё {countdown}."
WAR_COOLDOWN_ALERT = "Следующую войну можно объявить через {countdown}."
OUTGOING_WAR_EXISTS_ALERT = "Ты уже объявил войну — дождись её итога."
TARGET_AT_WAR_ALERT = "Этому императору уже объявлена война."
WAR_NOT_FOUND_ALERT = "Этого вызова уже нет."

# Итог.
WAR_HOW_ACCEPTED = "Бой принят — {rounds} раунд(ов)."
WAR_HOW_FORFEIT = "Защитник не принял вызов — бился его лагерь защиты ({rounds} раунд(ов))."
WAR_REPORT = (
    "{headline}\n{how}\n━━━━━━━━━━━━━━━━━━\n"
    "⚔️ {attacker}: мощь {att_power}, погибло {att_dead}\n"
    "🛡 {defender}: мощь {def_power}, погибло {def_dead}\n━━━━━━━━━━━━━━━━━━\n"
    "{spoils}"
)
WAR_ATTACKER_WON = "🏆 <b>Победа над императором {defender}!</b>"
WAR_ATTACKER_LOST = "💀 <b>Поражение в войне с {defender}.</b>"
WAR_DEFENDER_WON = "🛡 <b>Ты отбил войну императора {attacker}!</b>"
WAR_DEFENDER_LOST = "💀 <b>Император {attacker} победил тебя в войне.</b>"
WAR_SPOILS_CITIES = "🏙 Города перешли победителю: {cities}\n"
WAR_SPOILS_TREASURY = "🪙 Из казны проигравшего: {amount} NHCoin ({percent}%)\n"
WAR_SPOILS_BUSINESSES = "💼 Владений перешло вместе с городами: {count} зд.\n"
WAR_DEMOTED = "👑 Без городов {defender} теряет трон и возвращается в банду (армия и прокачка остаются).\n"
WAR_VOID = "⚔️ Война с {defender} отменена: к сроку кто-то уже не император или у защитника не осталось городов."
