"""Запрет боёв в стране: один ответ игроку на все места боя (хендлер ошибок)."""
from __future__ import annotations

from aiogram.types import ErrorEvent

from bot.services.country import BattlesClosedError
from bot.texts.country import BATTLES_CLOSED_ALERT


async def on_battles_closed(event: ErrorEvent) -> bool:
    """Сервис боя бросает `BattlesClosedError` до КД и списаний. Отвечаем там, откуда пришёл апдейт."""
    exc = event.exception
    text = BATTLES_CLOSED_ALERT.format(name=exc.country_name if isinstance(exc, BattlesClosedError) else "")
    update = event.update
    if update.callback_query is not None:
        await update.callback_query.answer(text, show_alert=True)
    elif update.message is not None:
        await update.message.answer(text)
    return True
