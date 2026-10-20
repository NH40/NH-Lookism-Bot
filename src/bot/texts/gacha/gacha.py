"""Крутки за тикеты — результат крутки, тикеты (тексты).

Popup-алерты (`callback.answer`) — БЕЗ HTML.
"""
from __future__ import annotations

from bot.utils.formatting import format_countdown

TICKETS_LINE = "🎟 Тикеты: {count}/{cap}{next}"
TICKETS_NEXT = " (следующий через {countdown})"
TICKETS_FULL = " (хранилище полное)"

ROLL_RESULT = (
    "🃏 <b>Вербовка уника</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{label}\n"
    "💎 Редкость: <b>{rarity}</b>\n"
    "💪 Мощь: <b>{power}</b>\n"
    "📌 Позиции: {positions}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{skills_line}"
    "{copies_line}\n"
    "{tickets_line}"
)
ROLL_SKILLS_LINE = "✨ {position}: {names}\n"
ROLL_PERK_LINE = "♾ Абсолют: {perk}\n"
ROLL_SKILLS_TAIL = "<i>Подробно — в карточке уника.</i>\n━━━━━━━━━━━━━━━━━━\n"
COPIES_NEW = "✨ Новая карта в коллекции! Копия ушла в армию — лагерь атаки."
COPIES_DUPLICATE = "Копия №{copies} — ушла в армию (лагерь атаки)."

BTN_ROLL = "🃏 Вербовка уника — 🎟 {count}/{cap}"
BTN_ROLL_AGAIN = "🃏 Крутить ещё"
BTN_COLLECTION = "📚 Коллекция"

# --- popup (без HTML) ---
NO_TICKETS = "Тикетов нет. Следующий через {countdown}."
ROLL_BUSY = "Обрабатываю…"


def tickets_line(count: int, cap: int, next_in_seconds: int | None) -> str:
    """«🎟 Тикеты: 7/10 (следующий через 12:34)» — принимает примитивы, не объект сервиса."""
    tail = TICKETS_FULL if next_in_seconds is None else TICKETS_NEXT.format(countdown=format_countdown(next_in_seconds))
    return TICKETS_LINE.format(count=count, cap=cap, next=tail)


# Массовое открытие (2026-10-21).
BTN_ROLL_MANY = "🃏 Открыть несколько"
ROLL_MANY_PROMPT = "🎟 Тикетов: <b>{count}</b>. Сколько открыть разом? Напиши число (до {max})."
ROLL_MANY_RESULT = (
    "🃏 <b>Открыто тикетов: {count}</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "{rarities}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "✨ Новых в коллекции: <b>{new}</b>{new_list}\n"
    "{free_line}"
    "Лучшая: {best}\n"
    "{tickets_line}{stopped}"
)
ROLL_MANY_RARITY_LINE = "{rarity}: <b>{count}</b>"
ROLL_MANY_FREE = "🎁 Тикет вернулся: {free} раз\n"
ROLL_MANY_STOPPED = "\n<i>Тикеты закончились — открыто, сколько хватило.</i>"
ROLL_MANY_INVALID = "Нужно целое число от 1."
