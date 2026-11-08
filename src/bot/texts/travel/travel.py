"""Переезд (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

BTN_TRAVEL = "🧳 Переезд"
BTN_TRAVEL_CITY = "🏙 Другой город страны"
BTN_TRAVEL_COUNTRY = "🌍 Другая страна"
BTN_TRAVEL_ABANDON = "🏳 Отказаться от районов"
BTN_TRAVEL_ABANDON_YES = "🏳 Да, отказаться"
BTN_TRAVEL_GO = "✅ Переехать"
BTN_BACK_TO_TRAVEL = "◀️ К переезду"
BTN_TO_MAP = "🗺 Карта"
BTN_OTHER_COUNTRY = "◀️ Другая страна"

TRAVEL_SCREEN = (
    "🧳 <b>Переезд</b>\n━━━━━━━━━━━━━━━━━━\n"
    "📍 Сейчас: <b>{country}</b>, {city}\n"
    "🏘 Твоих районов: <b>{districts}</b>{holdings_tail}\n"
    "━━━━━━━━━━━━━━━━━━\n{rules}{cooldown}"
)
HOLDINGS_TAIL = " в {cities} гор., зданий на них: {buildings}"
RULES_EMPEROR = "👑 Император не покидает страну, пока на троне. Между её городами — свободно.\n"
RULES_GANG_DISTRICTS = (
    "Пока у тебя есть районы, переехать нельзя. Откажись от них: районы уйдут ботам, "
    "здания на них сгорят. Армия, уники и развитие останутся.\n"
)
RULES_GANG = "Между городами страны — свободно. Сменить страну можно раз в {interval}.\n"
RULES_CIRCLE = (
    "Между городами страны — свободно, всё остаётся. Сменить страну можно раз в {interval}, "
    "но все районы и здания пропадут, и ты снова станешь бандой.\n"
)
COOLDOWN_LINE = "⏳ Сменить страну можно через <b>{countdown}</b>.\n"
CITY_COOLDOWN_LINE = "⏳ Следующий переезд через <b>{countdown}</b>.\n"
CHALLENGE_LINE = "⚔️ Против тебя висит вызов: отказаться от районов и сменить страну можно только после боя.\n"
RULES_INTERVAL_LINE = "Между переездами — {interval}.\n"

PICK_COUNTRY = "🌍 Выбери страну:"
PICK_CITY = "🏙 <b>{country}</b> — выбери город:"
CONFIRM_COUNTRY = (
    "🌍 <b>Переезд: {country}, {city}</b>\n━━━━━━━━━━━━━━━━━━\n"
    "Следующая смена страны — через {interval}.\n{losses}"
)
CONFIRM_LOSSES = (
    "⚠️ Ты потеряешь <b>{districts}</b> районов в {cities} гор. и <b>{buildings}</b> зданий и станешь бандой. "
    "Армия, уники и развитие останутся. Отменить нельзя.\n"
)
ABANDON_ASK = (
    "🏳 <b>Отказаться от районов?</b>\n━━━━━━━━━━━━━━━━━━\n"
    "<b>{districts}</b> районов уйдут ботам, <b>{buildings}</b> зданий сгорят. Отменить нельзя.\n"
    "Армия, уники и развитие останутся, после этого можно переезжать."
)
ABANDONED = "🏳 Ты отказался от {districts} районов, сгорело зданий: {buildings}. Теперь можно переезжать."
MOVED = "🧳 Ты переехал: <b>{country}</b>, {city}."
MOVED_LOST = "\nПотеряно: {districts} районов и {buildings} зданий. Теперь ты банда."

NOT_ONBOARDED_ALERT = "Сначала выбери страну и город: /start."
SAME_CITY_ALERT = "Ты уже в этом городе."
HAS_DISTRICTS_ALERT = "Сначала откажись от районов."
NO_DISTRICTS_ALERT = "У тебя нет районов."
EMPEROR_ALERT = "Император не покидает страну, пока на троне."
COOLDOWN_ALERT = "Сменить страну можно через {countdown}."
CITY_COOLDOWN_ALERT = "Следующий переезд через {countdown}."
CHALLENGE_PENDING_ALERT = "Против тебя висит вызов. Сначала бой или конец срока вызова."
UNKNOWN_CITY_ALERT = "Такого города нет."
