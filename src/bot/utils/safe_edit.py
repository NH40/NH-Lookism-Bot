from __future__ import annotations

from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def safe_edit_text(message: Message, text: str, **kwargs: Any) -> None:
    """edit_text, который проглатывает "message is not modified" — неизбежный побочный
    эффект повторных кликов (правило 2: пока обрабатывался первый клик, второй уже мог
    прилететь и отредактировать то же самое). Если редактировать нечего текстом (сообщение
    с фото — правило 12), удаляет и присылает заново. Портировано из Universe Anime Planet."""
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as exc:
        err = str(exc).lower()
        if "message is not modified" in err:
            return
        if "there is no text in the message to edit" in err:
            try:
                await message.delete()
            except TelegramBadRequest:
                pass
            await message.answer(text, **kwargs)
            return
        raise


async def safe_clear_markup(message: Message) -> None:
    """Убирает кнопки у сообщения (правило 11 — без явного пустого reply_markup они
    остались бы кликабельны), глотая "message is not modified" на повторном нажатии."""
    try:
        await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
