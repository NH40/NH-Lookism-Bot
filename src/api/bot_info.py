"""Имя бота (для кнопок «Открыть в боте» в Mini App) — один `getMe` на процесс."""
from __future__ import annotations

from aiogram import Bot

from bot.config.settings import get_settings

_username: str | None = None


async def get_bot_link() -> str | None:
    """`https://t.me/<username>` или None, если Telegram недоступен (кнопка тогда прячется)."""
    global _username
    if _username is None:
        bot = Bot(get_settings().bot_token)
        try:
            _username = (await bot.get_me()).username
        except Exception:
            return None
        finally:
            await bot.session.close()
    return f"https://t.me/{_username}" if _username else None
