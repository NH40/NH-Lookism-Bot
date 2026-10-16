"""Школы учителей статистов (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.constant.school import SCHOOL_AGILITY, SCHOOL_SPEED, SCHOOL_STRENGTH, SCHOOL_TECHNIQUE

SCHOOL_NAMES: dict[str, str] = {
    SCHOOL_STRENGTH: "Сила",
    SCHOOL_AGILITY: "Ловкость",
    SCHOOL_SPEED: "Скорость",
    SCHOOL_TECHNIQUE: "Техника",
}
SCHOOL_TEACHERS: dict[str, str] = {
    # Пользователь 2026-10-12: сила — Бэкхо, техника — Хансу, ловкость — Элита, скорость — Мусаши.
    SCHOOL_STRENGTH: "Бэкхо",
    SCHOOL_AGILITY: "Элита",
    SCHOOL_SPEED: "Мусаши",
    SCHOOL_TECHNIQUE: "Хансу",
}
SCHOOL_EFFECTS: dict[str, str] = {
    SCHOOL_STRENGTH: "мощь бойца +8% за уровень школы",
    SCHOOL_AGILITY: "уклонение +3% за уровень школы",
    SCHOOL_SPEED: "побег и контратака +2%, мощь +2% за уровень школы",
    SCHOOL_TECHNIQUE: "блок +3% и контратака +1% за уровень школы",
}
SCHOOL_TAG = " 🥋{name} {level}"

BTN_SCHOOL_EVENT = "📚 Учитель {teacher} · школа «{school}»"
TEACHER_SCREEN = (
    "📚 <b>Учитель статистов {teacher}</b> — школа «{school}»\n"
    "<i>{effect}</i>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{body}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⏳ Уйдёт с карты через <b>{countdown}</b>"
)
TEACHER_OFFER = "Возьми его задание — выполнишь, и учитель появится в 🛍 Магазине → Обучение.\n<i>Задание не сгорает, когда учитель уйдёт с карты — главное взять его, пока учитель здесь.</i>\n\n📜 <b>Задание:</b>\n{tasks}"
TEACHER_QUEST = "📜 <b>Задание учителя:</b>\n{tasks}"
TEACHER_QUEST_DONE = "\n\n✅ Задание выполнено — учитель ждёт тебя в магазине."
TEACHER_UNLOCKED = "✅ Учитель уже в твоём магазине (🛍 Магазин → Обучение)."
BTN_MEET = "🤝 Взять задание"
BTN_CLAIM = "🎁 Позвать в магазин"

SHOP_BLOCK = "\n\n━━━━━━━━━━━━━━━━━━\n📚 <b>Обучение</b> — учителя выводят статистов в свои школы.{lines}"
SHOP_EMPTY = "\nУчителей пока нет — они появляются на 🗺 Карте."
SHOP_LINE_LOCKED = "\n   · {teacher} («{school}») — купить за {price} 🪙"
SHOP_LINE_OWNED = "\n   · {teacher} («{school}») — куплен, занятия в 🏋 Тренировках → 🏫 Школы"
SHOP_COOLDOWN = ", ещё {countdown}"
SHOP_QUEST_LINE = "\n   · задание {teacher}: {done}"
BTN_BUY = "📚 Купить {teacher} · {price} 🪙"
BTN_LESSON = "🥋 Занятие у {teacher} · {price} 🪙"
BTN_CLAIM_SHOP = "🎁 Учитель {teacher} → в магазин"

PUSH_TEACHER = (
    "📚 На карте появился учитель статистов <b>{teacher}</b> (школа «{school}») — на {duration}.\n"
    "Возьми его задание на 🗺 Карте."
)
MET = "🤝 Учитель <b>{teacher}</b> даёт задание:\n{tasks}\n\nВыполнишь — он появится в 🛍 Магазине → Обучение. <i>Задание не сгорает, когда учитель уйдёт с карты.</i>"
CLAIMED = "📚 Учитель <b>{teacher}</b> теперь в твоём магазине — 🛍 Магазин → Обучение."
LESSON_DONE = "🥋 Занятие у {teacher}: в школу «{school}» вступили {joined}, подняли уровень школы {leveled}."
BOUGHT_ALERT = "Учитель {teacher} твой — занятия открыты"
TEACHER_GONE_ALERT = "Учитель уже ушёл с карты."
ALREADY_UNLOCKED_ALERT = "Этот учитель уже в твоём магазине."
QUEST_ACTIVE_ALERT = "Задание этого учителя у тебя уже есть."
QUEST_NOT_DONE_ALERT = "Задание учителя ещё не выполнено."
NOT_ENOUGH_ALERT = "Не хватает NHCoin: нужно {cost}."
COOLDOWN_ALERT = "Следующее занятие у этого учителя через {countdown}."
NO_STUDENTS_ALERT = "Некого учить: нет статистов без школы и учеников этой школы ниже максимума."
NOT_OWNED_ALERT = "Сначала купи этого учителя."
BUSY_ALERT = "Обрабатываю…"
