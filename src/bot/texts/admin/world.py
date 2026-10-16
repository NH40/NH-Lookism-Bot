"""Админка «Районы, города, императоры»: тексты."""
from __future__ import annotations

SEP = "━━━━━━━━━━━━━━━━━━"

WORLD_MENU = f"🗺 <b>Районы, города, императоры</b>\n{SEP}\n<i>Найдите город по названию — откроется карточка с районами и действиями.</i>"
BTN_FIND_CITY = "🔎 Найти город"
BTN_BACK = "◀️ Назад"
BTN_YES = "✅ Да, подтверждаю"
BTN_NO = "❌ Отмена"
BTN_SET_OWNER = "👤 Назначить владельца"
BTN_RESET = "🤖 Вернуть ботам"
BTN_SET_EMP = "👑 Назначить императора"
BTN_DEL_EMP = "🚫 Снять императора"
BTN_CANCEL_CH = "⚔️ Отменить вызовы на районы"
BTN_CANCEL_WAR = "🏰 Отменить войну императора"
BTN_TO_CITY = "◀️ К городу"

ASK_CITY = f"🔎 <b>Поиск города</b>\n{SEP}\nВведите название города (или его часть)."
CITY_NOT_FOUND = "Город не найден. Попробуйте другое название."
PICK_CITY = f"🔎 <b>Найдено несколько городов</b>\n{SEP}\n<i>Выберите нужный.</i>"
ASK_PLAYER = "Введите @ник или id игрока."
PLAYER_NOT_FOUND = "Игрок не найден. Введите @ник или id ещё раз."

CITY_CARD = (
    "🏙 <b>{name}</b> ({country})\n" + SEP + "\n"
    "👑 Император: <b>{emperor}</b>\n"
    "🏘 Районов: <b>{total}</b> (у ботов <b>{bots}</b>)\n"
    "⚔️ Висящих вызовов: <b>{challenges}</b>\n\n"
    "{districts}\n\n"
    "<i>Нажмите на номер района для действий.</i>"
)
DISTRICT_LINE = "{number}. {owner}"
OWNER_BOTS = "боты"

DISTRICT_CARD = (
    "🏘 <b>Район {number}</b> — {city}\n" + SEP + "\n"
    "Владелец: <b>{owner}</b>\n"
    "⚔️ Висящий вызов: <b>{challenge}</b>\n\n"
    "<i>Смена владельца начисляет доход бизнесов обеим сторонам, бизнесы остаются на районе.</i>"
)
CHALLENGE_NONE = "нет"
CHALLENGE_YES = "есть (игрок {attacker} → {defender})"

ASK_OWNER = f"👤 <b>Новый владелец района {{number}}</b>\n{SEP}\nВведите @ник или id игрока."
ASK_EMPEROR = f"👑 <b>Новый император города «{{city}}»</b>\n{SEP}\nВведите @ник или id игрока."

CONFIRM_RESET = f"⚠️ <b>Вернуть район {{number}} ботам?</b>\n{SEP}\nТекущий владелец <b>{{owner}}</b> потеряет район; бизнесы уйдут во «владения» (доход остаётся)."
CONFIRM_DEL_EMP = f"⚠️ <b>Снять императора с города «{{city}}»?</b>\n{SEP}\nГород перестанет платить налоги <b>{{emperor}}</b>."
CONFIRM_CANCEL_CH = f"⚠️ <b>Отменить вызовы на районы города «{{city}}»?</b>\n{SEP}\nВисящих вызовов: <b>{{count}}</b>."
CONFIRM_CANCEL_WAR = f"⚠️ <b>Отменить висящую войну императора {{emperor}}?</b>\n{SEP}\nВоен: <b>{{count}}</b>."

DONE_OWNER = "Готово: владелец района {number} — {owner}."
DONE_RESET = "Район {number} возвращён ботам."
DONE_EMP = "Император города «{city}» — {emperor}."
DONE_DEL_EMP = "Император с города снят."
DONE_CANCEL_CH = "Отменено вызовов: {count}."
DONE_CANCEL_WAR = "Отменено войн: {count}."
ALERT_ALREADY_BOTS = "Район уже у ботов."
ALERT_NO_EMPEROR = "У города нет императора."
ALERT_NOTHING = "Нечего отменять."
ALERT_STALE = "Состояние изменилось, откройте карточку заново."
ALERT_SAME_OWNER = "Игрок уже владеет этим районом."
