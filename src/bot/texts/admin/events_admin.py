"""Админка «События карты»: тексты."""
from __future__ import annotations

SEP = "━━━━━━━━━━━━━━━━━━"

MENU_HEAD = f"🎉 <b>События карты</b>\n{SEP}\n"
MENU_EMPTY = "Активных событий нет."
MENU_HINT = "\n\n<i>Нажмите на событие, чтобы снять его. События общие для всей карты, привязки к городу нет.</i>"
EVENT_LINE = "{icon} <b>{title}</b> — ещё {left}{clan}"
CLAN_TAG = " · клан <b>{clan_id}</b>"

BTN_SPAWN = "➕ Запустить событие"
BTN_BACK = "◀️ Назад"
BTN_REFRESH = "🔄 Обновить"
BTN_REMOVE = "🗑 Снять событие"
BTN_YES = "✅ Да, подтверждаю"
BTN_NO = "❌ Отмена"
BTN_PUSH = "📣 Запустить с оповещением"
BTN_NO_PUSH = "🤫 Запустить тихо"

KIND_TITLES = {"b": "👹 Босс", "t": "🥋 Учитель техник", "s": "🎓 Учитель статистов"}
KIND_ICONS = {"boss": "👹", "teacher": "🥋", "school": "🎓"}
KIND_NAMES = {"boss": "Босс", "teacher": "Учитель техник", "school": "Учитель статистов"}

EVENT_CARD = (
    "{icon} <b>{title}</b>\n" + SEP + "\n"
    "Вид: <b>{kind}</b>\nОсталось: <b>{left}</b>\nУчастников: <b>{entries}</b>{clan}"
)
CONFIRM_REMOVE = f"⚠️ <b>Снять событие «{{title}}»?</b>\n{SEP}\nИгроки больше не смогут с ним взаимодействовать, записи участия удалятся."

SPAWN_KIND = f"➕ <b>Запуск события</b>\n{SEP}\n<i>Выберите вид события.</i>"
SPAWN_CODE = f"➕ <b>{{kind}}</b>\n{SEP}\n<i>Выберите, кого запустить.</i>"
SPAWN_PUSH = f"➕ <b>{{title}}</b>\n{SEP}\nДлительность: <b>{{left}}</b>\n\n<i>Оповестить недавно заходивших игроков?</i>"

DONE_REMOVED = "Событие снято."
DONE_SPAWNED = "Событие запущено."
DONE_SPAWNED_PUSH = "Событие запущено, оповещение отправляется."
ALERT_GONE = "Событие уже закончилось или снято."
ALERT_DUPLICATE = "Такое событие уже идёт."
ALERT_STALE = "Устарело, откройте раздел заново."
