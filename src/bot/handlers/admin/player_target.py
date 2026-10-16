"""Админка: общие помощники действий над игроком (give/dev/punish): цель, имя, возврат в карточку."""
from __future__ import annotations

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.user import User
from bot.handlers.admin.players import render_card
from bot.texts.admin import players_admin as t
from bot.utils.formatting import esc
from bot.utils.safe_edit import safe_edit_text


async def load_target(callback: CallbackQuery, session: AsyncSession, user_id: int | None) -> User | None:
    """Цель действия; нет — алерт и None."""
    user = await session.get(User, user_id) if user_id is not None else None
    if user is None:
        await callback.answer(t.NOT_FOUND_ALERT, show_alert=True)
    return user


def name_of(user: User) -> str:
    return esc(user.display_name or user.username or str(user.id))


async def edit_screen(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def back_to_card(callback: CallbackQuery, session: AsyncSession, user_id: int, notice: str) -> None:
    """Вернуться в карточку игрока после изменения (сообщение редактируется)."""
    rendered = await render_card(session, callback.from_user.id, user_id)
    if rendered is None:
        await callback.answer(t.NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, t.NOTICE.format(text=notice) + rendered[0], reply_markup=rendered[1])


async def reply_card(message: Message, session: AsyncSession, user_id: int, notice: str) -> None:
    """То же после текстового ввода (новое сообщение)."""
    rendered = await render_card(session, message.from_user.id, user_id)
    if rendered is None:
        await message.answer(t.NOT_FOUND_ALERT)
        return
    await message.answer(t.NOTICE.format(text=notice) + rendered[0], reply_markup=rendered[1])


def parse_int(raw: str | None) -> int | None:
    """Целое со знаком без нуля (пробелы внутри допустимы); иначе None."""
    try:
        value = int((raw or "").replace(" ", ""))
    except ValueError:
        return None
    return value or None


def sign(value: int) -> str:
    return "+" if value > 0 else "−"


def parse_args(data: str, prefix: str) -> tuple[list[str], int] | None:
    """`prefix` + `поле:поле:...:uid` → (поля, uid); некорректное — None."""
    parts = data.removeprefix(prefix).split(":")
    if not parts or not parts[-1].isdigit():
        return None
    return parts[:-1], int(parts[-1])
