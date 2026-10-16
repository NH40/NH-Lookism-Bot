"""Battle Pass (тексты). Оформление — в стиле LBP 1.0."""
from __future__ import annotations

SEPARATOR = "━━━━━━━━━━━━━━━━━━"
PASS_HEADER = (
    "🎫 <b>Battle Pass · Сезон {season}</b>\n"
    "⏳ До конца сезона: <b>{season_left}</b>\n"
    "{sep}\n"
    "🏅 Уровень <b>{level}</b>{loop}\n"
    "{bar} {percent}% — {xp}/{level_xp} опыта\n"
    "{boost}\n"
    "{premium}\n"
    "📜 Свитков пропуска: <b>{scrolls}</b>\n"
    "{sep}\n"
    "<b>Уровни {low}–{high}</b>\n\n"
    "{rows}\n\n"
    "<i>Тап по 🎁 — забрать награду ячейки. Опыт дают задания дня.</i>"
)
LOOP_NOTE = " · 🔁 цикл после 500 ({pos}/10)"
BOOST_ON = "🚀 Буст <b>×{mult}</b>: {used}/{cap} ур. сегодня · сброс через {reset}"
BOOST_OFF = "🚀 Буст исчерпан · вернётся через {reset}"
PREMIUM_ON = "💎 Платная ветка: <b>открыта</b> ✅"
PREMIUM_OFF = "💎 Платная ветка: 🔒 закрыта — открыть за <b>{price}</b> 💎 на сезон"
LEVEL_ROW = "<b>{level}</b>{star}\n    {free_mark} 🆓 {free}\n    {premium_mark} 💎 {premium}"
STAR_CURRENT = " ⬅️ вы здесь"
MARK_CLAIMED = "✅"
MARK_READY = "🎁"
MARK_LOCKED = "🔒"
SCROLL_LABEL = "📜 Свиток"

CELL_CLAIMED = "✅{level}"
CELL_READY = "🎁{level}"
CELL_LOCKED = "🔒{level}"
CELL_NO_PREMIUM = "💎{level}"
BTN_PREV = "◀️"
BTN_NEXT = "▶️"
BTN_PAGE = "{page}/{pages}"
BTN_CLAIM_ALL_FREE = "🎁 Забрать всё 🆓"
BTN_CLAIM_ALL_PREMIUM = "🎁 Забрать всё 💎"
BTN_TO_QUESTS = "◀️ К заданиям"
BTN_BUY_PREMIUM = "💎 Открыть платную ветку — {price} 💎"

# Popup — без HTML.
BUSY_ALERT = "⏳ Подождите..."
LOCKED_ALERT = "🔒 Этот уровень ещё не открыт."
ALREADY_ALERT = "✅ Награда этого уровня уже получена."
NOT_PREMIUM_ALERT = "💎 Платная ветка не открыта."
NOTHING_ALERT = "Пока нечего забирать."
CLAIMED_ALERT = "🎁 Получено: {reward}"
PREMIUM_BOUGHT_ALERT = "💎 Платная ветка открыта до конца сезона! Забирай награды."
PREMIUM_ALREADY_ALERT = "Платная ветка уже открыта."
PREMIUM_NOT_ENOUGH_ALERT = "Не хватает донат-коинов: нужно {price}, у тебя {balance}. Пополнить — /donate"
CLAIMED_ALL_ALERT = "🎁 Забрано уровней: {count}\n{reward}"


def reward_text(reward: dict[str, int]) -> str:
    """«2 000 🪙, 1 🎫» — награда уровня (свиток — отдельный предмет, не ресурс)."""
    from bot.config.battle_pass import ITEM_SCROLL
    from bot.texts.resource import amount_label

    return ", ".join(
        f"{amount} {SCROLL_LABEL}" if code == ITEM_SCROLL else amount_label(code, amount) for code, amount in reward.items()
    ) or "—"
