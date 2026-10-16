"""События на карте — боссы и учителя (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.config.event import BOSS_POWER_PERCENT
from bot.constant.event import (
    BOSS_ELITE,
    BOSS_GAPRYONG,
    BOSS_JINYEONG,
    FRAGMENT_GENIUS,
    FRAGMENT_PATH,
    FRAGMENT_TECHNIQUE,
)

BOSS_NAMES: dict[str, str] = {
    BOSS_GAPRYONG: "Ким Гапрен",
    BOSS_JINYEONG: "Джинен",
    BOSS_ELITE: "Элита",
}
BOSS_ABILITIES: dict[str, str] = {
    BOSS_GAPRYONG: "После каждого убитого статиста становится сильнее — веди сильных бойцов и уников, "
    "толпа слабых его только накормит.",
    BOSS_JINYEONG: "Лечится, когда его бьют слабые, — только сильные статисты пробьют его восстановление.",
    BOSS_ELITE: "От его атак не увернуться — ловкость против него бесполезна, а сам он уходит от ударов.",
}
FRAGMENT_NAMES: dict[str, str] = {
    FRAGMENT_PATH: "фрагментов пути",
    FRAGMENT_TECHNIQUE: "фрагментов уникальных техник",
    FRAGMENT_GENIUS: "фрагментов гениальности",
}
FRAGMENT_EMOJI: dict[str, str] = {FRAGMENT_PATH: "🛤", FRAGMENT_TECHNIQUE: "🥋", FRAGMENT_GENIUS: "🧠"}

MAP_EVENTS_LINE = "\n⚡ <b>События на карте:</b> {count} — кнопки ниже\n"
BTN_EVENT_BOSS = "👹 {name} · {countdown}"
BTN_EVENT_BOSS_DONE = "✅ {name} повержен"

BOSS_SCREEN = (
    "👹 <b>Босс: {name}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>{ability}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "💪 Сила — <b>{percent}%</b> мощи твоего лагеря атаки.\n"
    "🎁 Награда за победу: {emoji} {fragment_name}.\n"
    "<i>Одна победа за появление, попытки — по обычному перерыву между боями.</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⏳ Уйдёт с карты через <b>{countdown}</b>"
)
BOSS_SCREEN_DONE = "\n\n✅ Ты уже победил этого босса — жди следующего появления."
BTN_FIGHT_BOSS = "⚔️ Сразиться"
BTN_BACK_TO_MAP = "◀️ К карте"

BOSS_WON = "🏆 <b>{name} повержен!</b>"
BOSS_LOST = "💀 <b>{name} оказался сильнее.</b>"
BOSS_RESULT = (
    "{headline}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🔁 Раундов: <b>{rounds}</b>\n"
    "⚔️ Твоя мощь: {power}, погибло: {dead}\n"
    "👹 Мощь босса: {boss_power}, осталось: {boss_left}\n"
    "{reward}"
)
BOSS_REWARD = "\n🎁 {emoji} +{fragments} {fragment_name}"

EVENT_GONE_ALERT = "Это событие уже ушло с карты."
BOSS_ALREADY_DEFEATED_ALERT = "Ты уже победил этого босса — жди следующего появления."

PUSH_BOSS_SPAWNED = (
    "👹 На карте появился босс <b>{name}</b> — на {duration}.\n"
    "Победа даст {emoji} {fragment_name}. Ищи его на 🗺 Карте."
)

BOSS_POWER_PERCENTS = BOSS_POWER_PERCENT
