"""Биржа (тексты). Popup-алерты — без HTML."""
from __future__ import annotations

from bot.constant.exchange import MODE_AUCTION, MODE_LOT, MODE_TRADE

EXCHANGE_SCREEN = (
    "📈 <b>Биржа</b>\n━━━━━━━━━━━━━━━━━━\n"
    "💱 Торговля между игроками любыми ресурсами и статистами.\n\n"
    "🛒 <b>Лоты</b> — продажа по цене, цену назначает продавец в любом ресурсе (комиссия {lot_fee}%).\n"
    "🔨 <b>Аукционы</b> — ставки, шаг +{step}%, ставка в последнюю минуту продлевает торги (комиссия {auc_fee}%).\n"
    "🤝 <b>Обмен</b> — прямое предложение игроку по юзернейму: ты ему предмет, он тебе цену.\n━━━━━━━━━━━━━━━━━━\n"
    "<i>Выставленное лежит в залоге — отменил, вернулось.</i>"
)
BTN_EXCHANGE = "📈 Биржа"
BTN_LOTS = "🛒 Лоты"
BTN_AUCTIONS = "🔨 Аукционы"
BTN_MINE = "📦 Мои сделки"
BTN_NEW_LOT = "➕ Продать"
BTN_NEW_AUCTION = "➕ Аукцион"
BTN_NEW_TRADE = "🤝 Обмен с игроком"
BTN_PREV = "◀️"
BTN_NEXT = "▶️"

LOTS_SCREEN = "🛒 <b>Лоты</b>\n━━━━━━━━━━━━━━━━━━\n{rows}"
LOTS_EMPTY = "📭 <i>Лотов нет.</i>"
LOT_ROW = "🛒 <b>#{id}</b> {item} — {price}\n"
BTN_LOT = "#{id} {item} · {price}"
LOT_SCREEN = "🛒 <b>Лот #{id}</b>\n━━━━━━━━━━━━━━━━━━\n📦 {item}\n💰 Цена: <b>{price}</b>\n👤 Продавец: {seller}"
BTN_BUY = "✅ Купить за {price}"

AUCTIONS_SCREEN = "🔨 <b>Аукционы</b>\n━━━━━━━━━━━━━━━━━━\n{rows}"
AUCTIONS_EMPTY = "📭 <i>Аукционов нет.</i>"
AUCTION_ROW = "🔨 <b>#{id}</b> {item} — {bid} · ещё {countdown}\n"
BTN_AUCTION = "#{id} {item} · {bid}"
AUCTION_SCREEN = (
    "🔨 <b>Аукцион #{id}</b>\n━━━━━━━━━━━━━━━━━━\n📦 {item}\n"
    "{bid_line}\n⬆️ Минимальная ставка сейчас: <b>{min_next}</b>\n⏳ До конца: {countdown}"
)
AUCTION_BID_LINE = "👑 Ставка лидера: <b>{bid}</b>{you}"
AUCTION_NO_BIDS = "🕊 Ставок ещё нет (старт {min_bid})."
AUCTION_YOU_LEAD = " — это ты"
BTN_BID_MIN = "🔨 Ставка {amount}"
BTN_BID_CUSTOM = "✍️ Своя ставка"
BID_PROMPT = "🔨 Ставка на аукцион <b>#{id}</b>\n⬆️ Не меньше <b>{min_next}</b>\n<i>Напиши число.</i>"

MINE_SCREEN = "📦 <b>Мои сделки</b>\n━━━━━━━━━━━━━━━━━━\n{body}"
MINE_LOTS = "🛒 <b>Лоты:</b>\n{rows}\n"
MINE_AUCTIONS = "🔨 <b>Аукционы:</b>\n{rows}\n"
MINE_INCOMING = "📥 <b>Тебе предлагают:</b>\n{rows}\n"
MINE_OUTGOING = "📤 <b>Ты предлагаешь:</b>\n{rows}\n"
MINE_EMPTY = "📭 <i>Сделок нет.</i>"
MINE_TRADE_ROW = "🤝 <b>#{id}</b> {item} за {price} — {who}, ещё {countdown}\n"
BTN_CANCEL_LOT = "❌ Снять лот #{id}"
BTN_CANCEL_AUCTION = "❌ Снять аукцион #{id}"
AUCTION_CANCELLED_ALERT = "Аукцион снят — предмет вернулся к тебе."
BTN_TRADE_ACCEPT = "✅ Принять #{id}"
BTN_TRADE_DECLINE = "❌ Отклонить #{id}"
BTN_TRADE_CANCEL = "↩️ Отозвать #{id}"

WIZARD_TITLE: dict[str, str] = {MODE_LOT: "➕ Продажа", MODE_AUCTION: "➕ Аукцион", MODE_TRADE: "🤝 Обмен"}
PICK_ITEM = "{title}\n━━━━━━━━━━━━━━━━━━\n<b>Что выставляешь?</b>"
BTN_ITEM_STATISTS = "👥 Статистов"
PICK_SQUAD = "{title}\n━━━━━━━━━━━━━━━━━━\n<b>Какой отряд?</b>\n<i>Бойцы берутся сначала из защиты, потом из атаки.</i>"
PICK_SQUAD_NONE = "У тебя нет статистов."
BTN_SQUAD = "{title} · {total}"
AMOUNT_PROMPT = "{title}: <b>{item}</b>\n👛 У тебя: <b>{have}</b>\n<i>Сколько выставить? Напиши число.</i>"
PICK_PRICE_RES = "{title}: {amount}\n━━━━━━━━━━━━━━━━━━\n<b>В чём {what}?</b>"
WHAT_PRICE = "цена"
WHAT_MIN_BID = "стартовая ставка"
PRICE_PROMPT = "{title}: {amount}\n━━━━━━━━━━━━━━━━━━\n💰 {what_cap}: <i>напиши число в {res}.</i>"
WHAT_PRICE_CAP = "Цена"
WHAT_MIN_BID_CAP = "Стартовая ставка"
PICK_HOURS = "{title}: {amount} · старт {price}\n━━━━━━━━━━━━━━━━━━\n<b>Сколько идут торги?</b>"
BTN_HOURS = "{hours} ч"
USERNAME_PROMPT = "{title}: {amount} за {price}\n━━━━━━━━━━━━━━━━━━\n<b>Кому предлагаешь?</b>\n<i>Напиши @юзернейм игрока.</i>"
CONFIRM_LOT = "{title}\n━━━━━━━━━━━━━━━━━━\n📦 {amount} за <b>{price}</b>\n💸 Комиссия при продаже: {fee}%"
CONFIRM_AUCTION = "{title}\n━━━━━━━━━━━━━━━━━━\n📦 {amount}, старт <b>{price}</b>, {hours} ч\n💸 Комиссия с итоговой ставки: {fee}%"
CONFIRM_TRADE = "{title}\n━━━━━━━━━━━━━━━━━━\n📦 Отдаёшь {amount} игроку {target} за <b>{price}</b>\n⏳ Предложение живёт {hours} ч"
BTN_CONFIRM = "✅ Выставить"
NUMBER_INVALID = "Нужно целое число больше нуля. Попробуй ещё раз."
DONE_LOT = "🛒 Лот #{id} выставлен."
DONE_AUCTION = "🔨 Аукцион #{id} начался."
DONE_TRADE = "🤝 Предложение #{id} отправлено."

PUSH_LOT_SOLD = "🛒 Твой лот купили: {item} → +{price} (минус комиссия {fee}%)."
PUSH_OUTBID = "🔨 Твою ставку {bid} перебили. Ставка вернулась — можешь поставить снова."
PUSH_AUCTION_WON = "🔨 Ты выиграл аукцион: {item} за {price}."
PUSH_AUCTION_SOLD = "🔨 Аукцион завершён: {item} продан за {price} (минус комиссия {fee}%)."
PUSH_AUCTION_UNSOLD = "🔨 Аукцион завершён без ставок — {item} вернулся к тебе."
PUSH_TRADE_OFFER = "🤝 Тебе предлагают обмен #{id}: {item} за {price} от {from_name}."
PUSH_TRADE_ACCEPTED = "🤝 Обмен принят: {item} → ты получил {price}."
PUSH_TRADE_DECLINED = "🤝 Обмен не состоялся: {item} вернулся к тебе."
PUSH_TRADE_EXPIRED = "🤝 Предложение обмена истекло — {item} вернулся к тебе."

# --- popup (без HTML) ---
ERRORS: dict[str, str] = {
    "busy": "Обрабатываю…",
    "bad_item": "Неверный предмет.",
    "bad_price": "Неверная цена.",
    "no_donate_auction": "Донат-коины нельзя выставлять на аукцион и нельзя ими торговаться на аукционе.",
    "bad_hours": "Неверный срок.",
    "too_many_lots": "Не больше {value} лотов сразу.",
    "too_many_auctions": "Не больше {value} аукционов сразу.",
    "too_many_trades": "Не больше {value} предложений обмена сразу.",
    "not_enough": "Столько нет.",
    "gone": "Сделка уже недоступна.",
    "own": "Это твоё же.",
    "no_money": "Не хватает: нужно {value}.",
    "low_bid": "Ставка слишком мала: минимум {value}.",
    "has_bids": "На аукционе уже есть ставка — снять его нельзя, дождись итога.",
    "no_player": "Игрок не найден.",
}
BOUGHT_ALERT = "Куплено: {item}"
BID_ALERT = "Ставка принята: {amount}"
ACCEPTED_ALERT = "Обмен состоялся: {item}"
DECLINED_ALERT = "Предложение закрыто"
CANCELLED_ALERT = "Лот снят, предмет вернулся"
