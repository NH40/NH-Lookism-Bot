"""Карта — город игрока и его районы (тексты)."""
from __future__ import annotations

MAP_HEADER = (
    "🗺 <b>{city}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "📍 Районов: <b>{total}</b>\n"
    "🏴 Твоих: <b>{mine}</b> · 🤖 у ботов: <b>{bots}</b> · 👥 у других игроков: <b>{others}</b>"
    "{sole}\n━━━━━━━━━━━━━━━━━━\n"
    "🌐 Твоё влияние: <b>{influence}</b>\n\n"
    "<i>Выбери район:</i>"
)
SOLE_OWNER_LINE = "\n👑 Весь город под контролем: <b>{owner}</b>"

DISTRICT_BTN_BOT = "№{number} · 🤖 боты · мощь {power}"
DISTRICT_BTN_MINE = "№{number} · 🏴 твой"
DISTRICT_BTN_OTHER = "№{number} · 🏴 {owner}"

# --- карта страны (круг и выше) ---
COUNTRY_MAP_HEADER = (
    "🌍 <b>{country}</b> — карта страны\n━━━━━━━━━━━━━━━━━━\n"
    "🏙 Городов: <b>{total}</b> · целиком твоих: <b>{mine}</b>\n"
    "🌐 Твоё влияние: <b>{influence}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Круг берёт город целиком: ботов города — одним боем, каждого игрока — вызовом за все его "
    "районы в этом городе. Выбери город:</i>"
)
# Император (жалоба 2026-10-12: «фулл страну захватил — кинуло обратно в круги»): его районы
# освобождены для других игроков, захватывать свою страну он не может — карта для обзора.
COUNTRY_MAP_HEADER_EMPEROR = (
    "👑 <b>{country}</b> — твоя империя\n━━━━━━━━━━━━━━━━━━\n"
    "🏙 Городов: <b>{total}</b> · 🌐 влияние: <b>{influence}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Ты император: районы страны освобождены для других игроков, твой бизнес работает во "
    "«Владениях», а с каждого дохода в стране тебе идут налоги. Захватывать свою страну император "
    "не может — его поле боя: 👑 Империя → ⚔️ Война императоров. Здесь — обзор городов:</i>"
)
CITY_EMPEROR_NOTE = "\n\n👑 <i>Это твоя империя — город для обзора. Воюй с другими императорами в 👑 Империи.</i>"
CITY_BTN = "{name} · 🤖{bots} 🏴{mine} 👥{owners}"
CITY_BTN_MINE = "👑 {name} — весь твой"
BTN_MY_CITY_DISTRICTS = "📍 Районы моего города"
BTN_BACK_TO_COUNTRY = "◀️ К карте страны"

CITY_SCREEN = (
    "🏙 <b>{name}</b> — {total} районов\n━━━━━━━━━━━━━━━━━━\n"
    "{bots_line}"
    "{owners_block}\n━━━━━━━━━━━━━━━━━━\n"
    "⚔️ Твой лагерь атаки: <b>{attack_quantity}</b> статистов, мощь <b>{attack_power}</b>"
)
CITY_BOTS_LINE = "🤖 Боты: <b>{districts}</b> р. — {quantity} статистов ранга {rank}, мощь <b>{power}</b>\n"
CITY_NO_BOTS_LINE = "🤖 Ботов в городе не осталось.\n"
CITY_OWNER_LINE = "🏴 {label}: {districts} р.{mark}"
CITY_OWNER_MINE = " — это ты"
CITY_OWNER_CHALLENGED = " — ⏳ вызов уже брошен"
CITY_NO_OWNERS = "👥 Игроков в городе нет."
CITY_FULLY_MINE = "\n\n👑 Весь город твой."
BTN_ATTACK_CITY_BOTS = "⚔️ Разбить ботов ({districts} р.)"
BTN_CHALLENGE_OWNER = "⚔️ Вызов: {label} ({districts} р.)"

# Бой за трон по кнопке (2026-10-20): круг, держащий все районы страны.
BTN_THRONE = "👑 Бой за трон"
THRONE_HINT_READY = "\n\n👑 <b>Вся страна твоя.</b> Её города держит император — вызови его на бой за трон."
THRONE_QUEUE_HEAD = "\nОчередь боёв по кнопке (по порядку, проиграл — дальше не идёт):"
THRONE_QUEUE_HOLDER = "\n{n}. 🏴 Освобождение у «{name}» — держит городов страны: {cities}"
THRONE_QUEUE_THRONE = "\n{n}. 👑 Трон: император «{name}»"
BTN_THRONE_NEXT = "⚔️ Бой: «{name}»"
THRONE_HINT_MISSING = "\n\n👑 Чтобы вызвать императора на бой за трон, захвати все районы страны — осталось <b>{missing}</b>."
THRONE_REPORT = "👑 <b>Бой за трон</b>\n━━━━━━━━━━━━━━━━━━{liberations}{throne}{crowned}"
THRONE_CROWNED = "\n\n🏆 <b>Ты — император страны!</b>"
THRONE_NOT_CONTENDER = "Вызвать на трон может только круг, держащий все районы своей страны."
THRONE_NOT_CONTENDER_MISSING = "Сначала захвати все районы страны — осталось {missing}."
THRONE_NO_TARGET = "Вызывать некого — страна свободна."
THRONE_COOLDOWN = "Бой ещё на кулдауне — через {countdown}."
