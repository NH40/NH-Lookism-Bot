"""Переиспользует тот же SQLAlchemy engine/session-фабрику, что и бот — общий
пакет bot.db, схема не дублируется. В отличие от Universe Anime Planet, этот API
read-WRITE почти целиком (подтверждено пользователем 2026-09-17: Mini App и бот —
оба в полном функционале) — но правило то же: вся бизнес-логика в services/<domain>,
роутер её не дублирует (см. CLAUDE.md, «Mini App»).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.db.session import make_engine, make_session_factory

_settings = get_settings()
engine = make_engine(_settings)
session_factory = make_session_factory(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
