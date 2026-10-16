"""Скрытность — родословная Куроды (сервис).

Пользователь 2026-10-02: «Курода — ниндзя… скрыть тебя в топе, скрытно провести шпионаж,
незаметность». Скрытый игрок (`EconomyMods.stealth`) показывается другим как «🥷
Неизвестный»: в отчётах PvP, войн императоров, на карте города; разведка его не видит ниже
3-го уровня (`services/intel`). Топы, когда появятся, используют этот же флаг.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.build import get_build
from bot.texts.stealth import STEALTH_LABEL


async def is_hidden(session: AsyncSession, user_id: int) -> bool:
    return (await get_build(session, user_id)).eco.stealth


async def label(session: AsyncSession, user_id: int, visible_label: str) -> str:
    """Подпись игрока для чужих глаз: скрытого — «Неизвестный»."""
    return STEALTH_LABEL if await is_hidden(session, user_id) else visible_label
