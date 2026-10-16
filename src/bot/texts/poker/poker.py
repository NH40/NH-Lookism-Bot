"""PvP-покер (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

LOBBY_SCREEN = (
    "♠️ <b>Покер</b> — техасский холдем с другими игроками на NHCoin.\n━━━━━━━━━━━━━━━━━━\n"
    "💡 Создай стол (бай-ин, 2–6 игроков, время ожидания) или сядь за открытый. Стек — это бай-ин; "
    "раздачи идут подряд, пока за столом есть хотя бы двое. На ход — {timeout} с, потом авто-чек "
    "или авто-фолд. Казино берёт 5% с банка.\n━━━━━━━━━━━━━━━━━━\n"
    "{tables}"
)
LOBBY_ROW = "🪑 <b>#{id}</b> · бай-ин {buy_in} 🪙 · {players}/{max} · старт через {countdown}\n"
LOBBY_EMPTY = "📭 <i>Открытых столов нет — создай свой.</i>"
BTN_CREATE = "➕ Создать стол"
BTN_JOIN = "🪑 #{id} · {buy_in} 🪙 · {players}/{max}"
BTN_MY_TABLE = "♠️ К моему столу"

CREATE_BUY_IN = "♠️ <b>Новый стол.</b> Бай-ин (он же стек каждого игрока):"
CREATE_PLAYERS = "♠️ Бай-ин {buy_in} 🪙. Сколько игроков за столом?"
CREATE_WAIT = "♠️ Бай-ин {buy_in} 🪙, до {players} игроков. Сколько ждать игроков?"
BTN_BUY_IN = "{buy_in} 🪙"
BTN_PLAYERS = "{n} игр."
BTN_WAIT = "{minutes} мин"

TABLE_WAITING = (
    "♠️ <b>Стол #{id}</b> · бай-ин {buy_in} 🪙 · блайнды {sb}/{bb}\n━━━━━━━━━━━━━━━━━━\n"
    "👥 Игроки ({players}/{max}):\n{seats}\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Старт через {countdown} (или как только стол заполнится).</i>"
)
TABLE_ACTIVE = (
    "♠️ <b>Стол #{id}</b> · раздача #{hand} · {street}\n"
    "🃏 Борд: {board}\n"
    "💰 Банк: <b>{pot}</b> 🪙 · блайнды {sb}/{bb}\n━━━━━━━━━━━━━━━━━━\n"
    "{seats}\n━━━━━━━━━━━━━━━━━━\n"
    "🂠 Твои карты: <b>{hole}</b>\n"
    "{turn}"
)
TABLE_CLOSED = "♠️ <b>Стол #{id}</b> закрыт. Стек вернулся на баланс."
SEAT_LINE = "{marker}{name} — {stack} 🪙{bet}{status}"
SEAT_TURN = "➡️ "
SEAT_IDLE = "▫️ "
SEAT_BET = " · ставка {bet}"
SEAT_FOLDED = " · сбросил"
SEAT_ALL_IN = " · олл-ин"
SEAT_DEALER = " 🔘"
SEAT_LEAVING = " · уходит"
BOARD_NONE = "—"
STREET_NAMES: dict[str, str] = {"preflop": "префлоп", "flop": "флоп", "turn": "тёрн", "river": "ривер", "showdown": "вскрытие"}
TURN_YOURS = "🟢 <b>Твой ход</b> (до {seconds} с): колл {call}"
TURN_YOURS_CHECK = "🟢 <b>Твой ход</b> (до {seconds} с): можно чек"
TURN_OTHER = "⏳ Ходит {name}"
TURN_NONE = ""

BTN_FOLD = "🏳 Фолд"
BTN_CHECK = "✔️ Чек"
BTN_CALL = "📞 Колл {amount}"
BTN_RAISE_MIN = "⬆️ Рейз до {amount}"
BTN_RAISE_POT = "⏫ Рейз до {amount}"
BTN_ALL_IN = "💥 Олл-ин {amount}"
BTN_REFRESH = "🔄 Обновить"
BTN_LEAVE = "🚪 Уйти"

RESULT = "🏁 <b>Раздача #{hand}</b> · банк <b>{pot}</b> 🪙\n━━━━━━━━━━━━━━━━━━\n{board}{lines}"
RESULT_BOARD = "🃏 Борд: {board}\n"
RESULT_LINE_SHOWDOWN = "👤 {name}: {hole} — {hand}{won}\n"
RESULT_LINE_FOLD_WIN = "🏆 {name} забирает банк — все остальные сбросили{won}\n"
RESULT_WON = " · <b>+{amount}</b>"
RESULT_CLOSED = "\n━━━━━━━━━━━━━━━━━━\n🚪 Стол закрыт: играть больше не с кем. Стеки вернулись на баланс."
HAND_NAMES = ("Старшая карта", "Пара", "Две пары", "Сет", "Стрит", "Флэш", "Фулл-хаус", "Каре", "Стрит-флэш")
CANCELLED = "♠️ Стол #{id} отменён: не набралось игроков. Бай-ин вернулся на баланс."
LEFT = "🚪 Ты вышел из-за стола #{id}, бай-ин вернулся."
LEAVING = "🚪 Встанешь из-за стола после этой раздачи — стек вернётся на баланс."

# --- popup (без HTML) ---
ERRORS: dict[str, str] = {
    "bad_params": "Неверные параметры стола.",
    "already_seated": "Ты уже сидишь за столом — сначала уйди с него.",
    "no_coins": "Не хватает NHCoin на бай-ин.",
    "table_gone": "Стол уже недоступен.",
    "table_full": "Стол уже заполнен.",
    "not_seated": "Ты не за этим столом.",
    "hand_gone": "Эта раздача уже закончилась.",
    "not_your_turn": "Сейчас не твой ход.",
    "cant_check": "Чек нельзя — есть ставка для колла.",
    "bad_raise": "Неверный рейз.",
    "bad_action": "Неизвестное действие.",
}
CREATED_ALERT = "Стол создан — ждём игроков"
JOINED_ALERT = "Ты за столом"
