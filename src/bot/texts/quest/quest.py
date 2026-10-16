"""Ежедневные задания (тексты). Оформление — как в LBP 1.0 (статус, эмодзи, полоса 🟩⬛)."""
from __future__ import annotations

from bot.constant.dev_quest import (
    TASK_BOSS_WIN,
    TASK_BP_CLAIM,
    TASK_BUILD,
    TASK_CASINO,
    TASK_CLAN_DONATE,
    TASK_COLLECT,
    TASK_CONTRACT,
    TASK_DEPOSIT,
    TASK_DEV_LEVEL,
    TASK_EXCHANGE_DEAL,
    TASK_EXCHANGE_LIST,
    TASK_GARRISON,
    TASK_INCOME,
    TASK_PERSONAL_TRAIN,
    TASK_POKER_HAND,
    TASK_POTION,
    TASK_PVP_CHALLENGE,
    TASK_RECRUIT,
    TASK_ROLL,
    TASK_SCHOOL_LESSON,
    TASK_STAT_INVEST,
    TASK_STORAGE,
    TASK_TRAIN_EXTRAS,
    TASK_WIN_PVE,
    TASK_WIN_PVP,
)

TASK_EMOJI: dict[str, str] = {
    TASK_WIN_PVE: "🥊", TASK_WIN_PVP: "⚔️", TASK_BOSS_WIN: "👹", TASK_PERSONAL_TRAIN: "🏋️",
    TASK_TRAIN_EXTRAS: "💪", TASK_RECRUIT: "👥", TASK_ROLL: "🎰", TASK_COLLECT: "💰", TASK_BUILD: "🏗",
    TASK_SCHOOL_LESSON: "🏫", TASK_POTION: "🧪", TASK_CASINO: "🎲", TASK_POKER_HAND: "🃏",
    TASK_EXCHANGE_DEAL: "🤝", TASK_EXCHANGE_LIST: "📦", TASK_DEPOSIT: "🏦", TASK_STORAGE: "🗄",
    TASK_CONTRACT: "📜", TASK_CLAN_DONATE: "🏛", TASK_GARRISON: "🛡", TASK_STAT_INVEST: "📈",
    TASK_DEV_LEVEL: "🌀", TASK_PVP_CHALLENGE: "📣", TASK_BP_CLAIM: "🎫", TASK_INCOME: "💵",
}
TIER_EMOJI: tuple[str, ...] = ("🟢", "🟡", "🟠", "🔴")

SEPARATOR = "━━━━━━━━━━━━━━━━━━"
QUESTS_HEADER = (
    "📋 <b>Ежедневные задания</b>\n"
    "⏰ Новые через: <b>{reset}</b>\n"
    "✅ Выполнено: <b>{completed}/{total}</b>{mult}\n"
    "♻️ {reroll}"
)
NEXT_MULT = " · следующее: опыт <b>×{mult}</b>"
ALL_DONE = " · 🌟 все выполнены!"
QUEST_ROW = (
    "{status} {emoji} <b>{label}</b> {tier_emoji}\n"
    "    {bar} {percent}% — {progress}/{target}\n"
    "    ✨ +{xp} опыта пасса"
)
QUESTS_FOOTER = "🎫 Опыт сразу идёт в Battle Pass · 📜 Свитков пропуска: <b>{scrolls}</b>"
STATUS_DONE = "✅"
STATUS_TODO = "🔄"
REROLL_FULL_OR_SWAP = "Реролл: <b>доступен</b> — все невыполненные или до {swaps} замен"
REROLL_SWAPS_LEFT = "Замен осталось: <b>{swaps}</b>"
REROLL_NONE = "Реролл: использован"

BTN_REROLL_ALL = "♻️ Переролить все"
BTN_SWAP = "🔁 Заменить одно"
BTN_BATTLE_PASS = "🎫 Battle Pass"
BTN_SCROLL = "📜 Свиток пропуска"
BTN_SWAP_SLOT = "{emoji} {label} — {progress}/{target}"
BTN_BACK_TO_QUESTS = "◀️ К заданиям"

SWAP_PICK = "🔁 <b>Какое задание заменить?</b>\nВыполненные не меняются, прогресс заменённого сгорит."
SCROLL_PICK = (
    "📜 <b>Свиток пропуска</b> — у вас: <b>{scrolls}</b>\n"
    "Сразу выполняет задание развития; награду заберите на его экране, как обычно.\n"
    "Пробуждение свитком не пропускается."
)
SCROLL_NONE = "Нет заданий развития, которые можно пропустить."
SCROLL_QUEST_CONVICTION = "Подтверждение убеждений"
SCROLL_QUEST_TEACHER = "Учитель техники: {name}"
SCROLL_QUEST_SCHOOL = "Учитель школы: {name}"

# Popup — без HTML.
BUSY_ALERT = "⏳ Подождите..."
REROLL_USED_ALERT = "Реролл на сегодня уже использован."
REROLLED_ALERT = "♻️ Задания обновлены!"
QUEST_DONE_ALERT = "Это задание уже выполнено."
QUEST_GONE_ALERT = "Задание уже сменилось — экран обновлён."
NO_SCROLL_ALERT = "Нет свитков пропуска. Они выпадают в Battle Pass."
SCROLL_USED_ALERT = "📜 Задание выполнено свитком! Заберите награду на его экране."
SCROLL_GONE_ALERT = "Это задание уже нельзя пропустить."

# --- тест для админов (2026-10-12) ---
BTN_ADMIN_COMPLETE = "🧪 Выполнить все задания (админ)"
ADMIN_COMPLETED_ALERT = "🧪 Выполнено: ежедневных {daily}, квестов развития {dev}. Награды квестов развития — на экранах систем."
