from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup


async def notify(bot: Bot, user_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> bool:
    """Проактивное сообщение в личку (вызов защитнику, итог боя обоим). Ошибку доставки
    молча глотаем — получатель мог заблокировать бота или удалить аккаунт, это не повод
    падать посреди чужого действия (вызов/бой к этому моменту уже закоммичен). Порт из
    Universe Anime Planet, плюс `reply_markup` (кнопка "Принять бой")."""
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
    except TelegramAPIError:
        return False
    return True
