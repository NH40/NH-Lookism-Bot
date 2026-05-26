from datetime import datetime, timezone
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import user_repo
from app.config import settings


def _ban_text(user) -> str:
    from app.utils.formatters import fmt_ttl
    if user.ban_until is None:
        until_str = "навсегда"
    else:
        secs = max(0, int((user.ban_until - datetime.now(timezone.utc)).total_seconds()))
        until_str = f"ещё {fmt_ttl(secs)}"
    reason = user.ban_reason or "причина не указана"
    return (
        f"🚫 <b>Вы заблокированы</b>\n\n"
        f"Причина: {reason}\n"
        f"Срок: {until_str}\n\n"
        f"По вопросам обращайтесь к администрации."
    )


class UserLoaderMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)

        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user:
            user, is_new = await user_repo.get_or_create(
                session,
                tg_id=tg_user.id,
                full_name=tg_user.full_name,
                username=tg_user.username,
            )
            data["user"] = user
            data["is_new_user"] = is_new

            # ── Проверка бана ─────────────────────────────────────────────
            # Администраторы проходят всегда.
            if tg_user.id not in settings.admin_ids_list and getattr(user, "is_banned", False):
                now = datetime.now(timezone.utc)
                ban_until = getattr(user, "ban_until", None)

                # Временный бан истёк — снимаем автоматически
                if ban_until is not None and ban_until <= now:
                    user.is_banned = False
                    user.ban_until = None
                    user.ban_reason = None
                    await session.flush()
                    # Пропускаем дальше как незабаненного
                else:
                    # Активный бан — блокируем событие
                    text = _ban_text(user)
                    if isinstance(event, Message):
                        await event.answer(text, parse_mode="HTML")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 Вы заблокированы", show_alert=True)
                    return  # не вызываем handler

        return await handler(event, data)