from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

# /cancel уже штатно чистит state сама — не нужно делать это дважды, и не нужно "съедать"
# апдейт до того, как её собственный хендлер отработает.
_EXEMPT_COMMANDS = {"/cancel"}


class CommandStateResetMiddleware(BaseMiddleware):
    """Любая слэш-команда, присланная пока висит незакрытое FSM-состояние, иначе молча
    проглатывалась бы хендлером ЭТОГО состояния как "невалидный ввод" — тот повторяет
    подсказку и не чистит state, поэтому ни одна команда не работает, пока игрок сам не
    пришлёт /cancel (известный класс бага в Universe Anime Planet — см. её CLAUDE.md).
    Сбрасываем состояние здесь, ДО того как апдейт дойдёт до роутеров конкретных
    FSM-флоу — тогда команда обрабатывается тем, для кого она реально предназначена."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        text = event.text
        if text and text.startswith("/") and text.split()[0].lower() not in _EXEMPT_COMMANDS:
            state = data.get("state")
            if state is not None and await state.get_state() is not None:
                await state.clear()
        return await handler(event, data)
