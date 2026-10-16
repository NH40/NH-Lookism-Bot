"""Казино (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.constant.casino import GAME_BLACKJACK, GAME_SLOTS

CASINO_SCREEN = (
    "🎰 <b>Казино</b>\n━━━━━━━━━━━━━━━━━━\n"
    "💰 Ставь любой ресурс. В блэкджеке можно ставить и статистов (не меньше 5).\n━━━━━━━━━━━━━━━━━━\n"
    "🎰 <b>Слоты</b> — три барабана: тройка умножает ставку (🍒×2 … ⭐×100), пара возвращает её.\n"
    "🃏 <b>Блэкджек</b> — против дилера: победа ×2, блэкджек с двух карт ×2.5, ничья — ставка назад.\n"
    "♠️ <b>Покер</b> — техасский холдем за столом с другими игроками на NHCoin."
)
GAME_NAMES: dict[str, str] = {GAME_SLOTS: "🎰 Слоты", GAME_BLACKJACK: "🃏 Блэкджек"}
BTN_POKER = "♠️ Покер"
BTN_CASINO = "🎰 Казино"

PICK_STAKE = "{game}\n━━━━━━━━━━━━━━━━━━\n<b>Чем ставишь?</b>"
BTN_STAKE_STATISTS = "👥 Статистами"
PICK_SQUAD = "{game}\n━━━━━━━━━━━━━━━━━━\n<b>Каким отрядом ставишь?</b>\n<i>Бойцы берутся сначала из защиты, потом из атаки.</i>"
PICK_SQUAD_NONE = "У тебя нет статистов."
BTN_SQUAD = "{title} · {total}"
STAKE_PROMPT = "{game} · ставка: <b>{item}</b>\n👛 У тебя: <b>{have}</b>\n<i>Сколько ставишь? Напиши число.</i>"
STAKE_INVALID = "Нужно целое число больше нуля. Попробуй ещё раз."

SLOTS_RESULT = "🎰 <b>[ {reel} ]</b>\n━━━━━━━━━━━━━━━━━━\n{line}"
SLOTS_TRIPLE = "🎉 Тройка! Ставка {stake} → выигрыш <b>{payout}</b>"
SLOTS_PAIR = "🤝 Пара — ставка {stake} возвращается."
SLOTS_LOSS = "💨 Мимо. Ставка {stake} проиграна."
BTN_SLOTS_AGAIN = "🔁 Ещё раз · {stake}"

BJ_TABLE = (
    "🃏 <b>Блэкджек</b> · ставка {stake}{doubled}\n━━━━━━━━━━━━━━━━━━\n"
    "🎩 Дилер: {dealer} {dealer_total}\n"
    "🙂 Ты: {player} <b>({player_total})</b>\n━━━━━━━━━━━━━━━━━━\n"
    "{status}"
)
BJ_DOUBLED = " ×2"
BJ_HIDDEN = "🂠"
BJ_YOUR_MOVE = "👉 <i>Твой ход.</i>"
BJ_RESULT: dict[str, str] = {
    "win": "🏆 Победа! Выигрыш <b>{payout}</b>",
    "natural": "🃏 Блэкджек! Выигрыш <b>{payout}</b>",
    "push": "🤝 Ничья — ставка {payout} возвращается.",
    "loss": "💀 Дилер сильнее. Ставка проиграна.",
    "bust": "💥 Перебор. Ставка проиграна.",
}
BTN_BJ_HIT = "➕ Ещё"
BTN_BJ_STAND = "✋ Хватит"
BTN_BJ_DOUBLE = "✖️2 Удвоить"
BTN_BJ_AGAIN = "🔁 Новая раздача"

# --- popup (без HTML) ---
X3_ALERT = "Казино просит вас остановиться: вы каждый раз ставите втрое больше. Измените размер ставки."
NOT_ENOUGH_ALERT = "Не хватает на ставку."
HAND_GONE_ALERT = "Эта раздача уже закончилась."
HAND_IN_PROGRESS_ALERT = "У тебя уже идёт раздача — доиграй её."
STATISTS_MIN_ALERT = "Статистами — не меньше 5 бойцов."
BUSY_ALERT = "Обрабатываю…"
