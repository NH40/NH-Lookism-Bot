"""Тренировки — личная (очки развития, КД 1 час) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML.
"""
from __future__ import annotations

TRAIN_MENU_HEADER = (
    "🏋️ <b>Тренировки</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{personal_line}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🏋️ <b>Тренировка статистов</b>\n{army_block}"
)

TRAIN_NO_EXTRAS = "Нечего тренировать — сначала заверби хотя бы одного статиста."

TRAIN_RESULT = (
    "🏋️ <b>Тренировка завершена</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "👥 Участвовало: <b>{attempted}</b>\n"
    "💪 Подняли мощь (×1.2): <b>{stage1}</b>\n"
    "⭐ Получили звезду пробуждения: <b>{stage2}</b>\n"
    "🏅 Повысили ранг: <b>{stage3}</b>"
)

TRAIN_COOLDOWN = "⏳ Тренировка ещё на кулдауне — попробуй через {countdown}."


# --- личная тренировка ---
PERSONAL_READY = "🧘 Личная тренировка: готова (потенциал — {potential}, очков развития: {points})"
PERSONAL_COOLDOWN_LINE = "🧘 Личная тренировка: через {countdown} (очков развития: {points})"
PERSONAL_RESULT = (
    "🧘 <b>Личная тренировка</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{outcome}\n"
    "🧬 Потенциал: <b>{potential}</b>\n"
    "🎯 Очков развития: <b>{points}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Следующая — через {countdown}. Вложи очки в характеристики.</i>"
)
PERSONAL_GAINED = "✅ Получено очков развития: <b>+{gained}</b>"
PERSONAL_NOTHING = "😓 В этот раз не вышло — очков не получено."
BTN_PERSONAL_TRAINING = "🧘 Личная тренировка"
BTN_TO_STATS = "📊 Характеристики"
# popup (без HTML)
PERSONAL_COOLDOWN = "⏳ Личная тренировка ещё на кулдауне — через {countdown}."

# --- тренировка техники (2026-10-12) ---
BTN_TECH_TRAINING = "🥋 Тренировка техники"
TECH_LIST = (
    "🥋 <b>Тренировка техники</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Каждый уровень техники открывается так: выбери технику → оплати тренировку у её учителя → "
    "выполни его квест → подними уровень за 🧩 фрагменты техники.\n━━━━━━━━━━━━━━━━━━\n"
    "🧩 Фрагментов: <b>{fragments}</b> · 🪙 NHCoin: <b>{coins}</b>"
)
TECH_LIST_EMPTY = "\n\n<i>Техник пока нет — их дают учителя на 🗺 карте.</i>"
BTN_TECH_ROW = "{mark} {name} · ур. {level}"
TECH_MARK = {"pay": "💰", "quest": "📜", "level": "⬆️", "max": "🏆"}
TECH_SCREEN = (
    "🥋 <b>{name}</b> — уровень <b>{level}/{max_level}</b>\n"
    "👤 Учитель: <b>{teacher}</b>\n━━━━━━━━━━━━━━━━━━\n{body}"
)
TECH_STAGE_PAY = (
    "Тренировка на уровень <b>{next}</b> у учителя — <b>{price}</b> 🪙.\n"
    "После оплаты учитель даст квест:\n{tasks}\n\n"
    "Выполнишь — поднимешь уровень за <b>{fragments}</b> 🧩 (у тебя {have})."
)
TECH_STAGE_QUEST = "📜 <b>Квест учителя</b> на уровень {next}:\n{tasks}\n\n<i>Квест не сгорает. Потом — {fragments} 🧩.</i>"
TECH_STAGE_LEVEL = "✅ Квест выполнен! Подними уровень {next} за <b>{fragments}</b> 🧩 (у тебя {have})."
TECH_STAGE_MAX = "🏆 Техника на максимальном уровне."
BTN_TECH_PAY = "💰 Оплатить тренировку · {price} 🪙"
BTN_TECH_LEVEL = "⬆️ Уровень {next} · {fragments} 🧩"
BTN_BACK_TO_TECH_LIST = "◀️ К техникам"
BTN_BACK_TO_TRAINING = "◀️ К тренировкам"
TECH_PAID_ALERT = "Тренировка оплачена — учитель дал квест."
TECH_ACTIVE_ALERT = "Тренировка на этот уровень уже оплачена — выполняй квест."
TECH_NOT_ENOUGH_COINS = "Не хватает NHCoin: нужно {cost}, у тебя {balance}."
TECH_NEED_TRAINING_ALERT = "Сначала тренировка у учителя: 🏋 Тренировки → 🥋 Тренировка техники."

# --- школы статистов (2026-10-13) ---
BTN_SCHOOLS = "🏫 Школы статистов"
SCHOOLS_SCREEN = (
    "🏫 <b>Школы статистов</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Учитель выводит статистов в свою школу: занятие — {price} 🪙, раз в час на школу. На занятии "
    "тренируются {coverage}% статистов: новички вступают в школу ({join}%), ученики поднимают её "
    "уровень ({level_up}%), до {max_level} уровней.\n━━━━━━━━━━━━━━━━━━\n{lines}"
)
SCHOOL_LINE_OWNED = "✅ <b>{teacher}</b> — школа «{school}»: {effect}{cooldown}"
SCHOOL_LINE_UNLOCKED = "🔓 <b>{teacher}</b> — школа «{school}»: учитель ждёт в 🛍 Магазине → Обучение ({price} 🪙)"
SCHOOL_LINE_LOCKED = "🔒 <b>{teacher}</b> — школа «{school}»: встреть учителя на 🗺 карте и выполни его задание"
SCHOOL_COOLDOWN = " · занятие через {countdown}"
BTN_SCHOOL_LESSON = "🥋 {teacher} · {price} 🪙"
BTN_SCHOOL_LESSON_CD = "⏳ {teacher} · {countdown}"
