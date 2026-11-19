"""Бот живёт и в группах/каналах (пользователь 2026-11-20): обычные сообщения игроков там не трогаем и не отвечаем
на них — только команды, кнопки и ввод своего FSM-состояния."""
from __future__ import annotations

from aiogram.types import Message, TelegramObject


def is_group_noise(event: TelegramObject) -> bool:
    """Обычное сообщение в группе (не команда) — молчим."""
    return isinstance(event, Message) and event.chat.type != "private" and not (event.text or "").startswith("/")
