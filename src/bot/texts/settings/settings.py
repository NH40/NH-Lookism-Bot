"""Настройки (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.constant.settings import (
    NOTIFY_CD_BATTLE,
    NOTIFY_CD_EXTRAS,
    NOTIFY_ARKHANGEL,
    NOTIFY_CD_PERSONAL,
    NOTIFY_BOSS,
    NOTIFY_CLAN,
    NOTIFY_CLAN_WAR,
    NOTIFY_EXCHANGE,
    NOTIFY_MASTERY,
    NOTIFY_POTION,
    NOTIFY_PVP_CALL,
    NOTIFY_PVP_REPORT,
    NOTIFY_SABOTAGE,
    NOTIFY_SCHOOL,
    NOTIFY_TEACHER,
    NOTIFY_THRONE,
    NOTIFY_WAR_CALL,
    NOTIFY_WAR_REPORT,
)

SETTINGS_SCREEN = "⚙️ <b>Настройки</b>\n━━━━━━━━━━━━━━━━━━\n<i>Выбери раздел:</i>"
BTN_BACK_TO_SETTINGS = "◀️ В настройки"

BTN_NOTIFICATIONS = "🔔 Уведомления"
NOTIFY_SCREEN = (
    "🔔 <b>Уведомления</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Включай и выключай пуши бота по одному. Выключенное просто не приходит — сама механика "
    "работает как обычно.\n━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <i>Вызов на бой и объявление войны можно принять только кнопкой из пуша или зайдя в "
    "бота — выключив их, легко пропустить окно и проиграть без боя.</i>"
)
NOTIFY_LABELS: dict[str, str] = {
    NOTIFY_PVP_CALL: "⚔️ Вызов на бой за район/город",
    NOTIFY_PVP_REPORT: "📜 Итог PvP-боя",
    NOTIFY_THRONE: "👑 Бой за мой трон",
    NOTIFY_WAR_CALL: "🏴 Объявление войны императоров",
    NOTIFY_WAR_REPORT: "📜 Итог войны императоров",
    NOTIFY_SABOTAGE: "🕵️ Саботаж против меня",
    NOTIFY_MASTERY: "🧱 Новый этап мастерства",
    NOTIFY_BOSS: "👹 Босс на карте",
    NOTIFY_TEACHER: "🥋 Учитель техник на карте",
    NOTIFY_SCHOOL: "📚 Учитель статистов на карте",
    NOTIFY_POTION: "🧪 Авто-зелье выключилось",
    NOTIFY_EXCHANGE: "📈 Биржа: продажи, ставки, обмены",
    NOTIFY_CLAN: "🏰 Клан: заявки, приглашения, обменник",
    NOTIFY_CLAN_WAR: "🏴 Война кланов",
    NOTIFY_CD_BATTLE: "⚔️ Можно атаковать (КД прошёл)",
    NOTIFY_CD_PERSONAL: "🧘 Личная тренировка готова",
    NOTIFY_CD_EXTRAS: "🏋 Тренировка статистов готова",
    NOTIFY_ARKHANGEL: "♾ Архангел: часовой доход",
}
NOTIFY_ON = "✅"
NOTIFY_OFF = "🔕"
BTN_NOTIFY_ALL_ON = "✅ Включить все"
BTN_NOTIFY_ALL_OFF = "🔕 Выключить все"
NOTIFY_TOGGLED_ON = "Включено: {label}"
NOTIFY_TOGGLED_OFF = "Выключено: {label}"
