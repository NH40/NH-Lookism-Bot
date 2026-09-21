from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BANNED_TEXT = "⛔️ Ваш аккаунт заблокирован."

# Один и тот же UPDATE обслуживает и бан-чек, и трекинг активности (User.last_active_at —
# "онлайн за 24ч" в статистике /admin) — не отдельным запросом на каждый апдейт (правило 4).
_TOUCH_SQL = text(
    """
    UPDATE users SET last_active_at = now() WHERE id = :user_id RETURNING is_banned
    """
)


class BanCheckMiddleware(BaseMiddleware):
    """Должна регистрироваться после DbSessionMiddleware — читает data['session'].
    Для ещё не зарегистрированных пользователей (нет строки в users) ничего не трогает
    и пропускает дальше — их создаст хендлер /start."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.successful_payment is not None:
            # Деньги уже списаны Telegram-ом до доставки этого апдейта — начисление
            # обязано пройти, даже если игрока успели забанить между отправкой инвойса
            # и приходом successful_payment.
            return await handler(event, data)

        session: AsyncSession = data["session"]
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        result = await session.execute(_TOUCH_SQL, {"user_id": tg_user.id})
        row = result.one_or_none()
        await session.commit()

        if row is not None and row.is_banned:
            if isinstance(event, Message):
                await event.answer(BANNED_TEXT)
            elif isinstance(event, CallbackQuery):
                await event.answer(BANNED_TEXT, show_alert=True)
            return None

        return await handler(event, data)
