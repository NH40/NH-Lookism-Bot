from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config.admin import LOG_SLOW_BOT_MS
from bot.services.country import BattlesClosedError
from bot.services.error_log import normalize, record_slow
from bot.utils.log_context import reset_source, reset_user, set_source, set_user

log = logging.getLogger(__name__)


def _describe(event: TelegramObject) -> str:
    if isinstance(event, CallbackQuery):
        return f"cb:{event.data or ''}"
    if isinstance(event, Message):
        if event.successful_payment:
            return "pay:telegram"
        if event.text and event.text.startswith("/"):
            return f"cmd:{event.text.split()[0]}"
        return "msg"
    return "bot"


class LogContextMiddleware(BaseMiddleware):
    """Самая внешняя: запоминает игрока и кнопку для журналов, ловит ошибку с этим контекстом и засекает
    медленные апдейты."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        source = _describe(event)
        from_user = getattr(event, "from_user", None)
        source_token, user_token = set_source(source), set_user(from_user.id if from_user else None)
        started = time.perf_counter()
        try:
            return await handler(event, data)
        except BattlesClosedError:  # ожидаемый отказ, его разбирает общий обработчик
            raise
        except Exception:
            log.exception("Ошибка обработки апдейта")
            raise
        finally:
            ms = int((time.perf_counter() - started) * 1000)
            if ms >= LOG_SLOW_BOT_MS:
                record_slow("bot", normalize(source), ms)
            reset_source(source_token)
            reset_user(user_token)
