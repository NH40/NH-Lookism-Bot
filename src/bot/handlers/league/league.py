"""Лиги: пуши о повышении и фоновый проход. Экранов нет: новая страна выбирается в обычном меню выбора страны."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.league import LEAGUE_INCOME_STEP, LEAGUE_POWER_STEP, LEAGUE_SWEEP_TICK_SECONDS, LEAGUES
from bot.keyboards.start import country_menu
from bot.services.country import closed_entries
from bot.services.league import daily_sweep, sweep_due
from bot.texts.league import PROMOTED
from bot.utils.notify import notify

log = logging.getLogger(__name__)
_PUSHES_PER_SECOND = 20


async def send_promotions(bot: Bot, session_factory: async_sessionmaker[AsyncSession], promoted: list[tuple[int, int]]) -> None:
    async with session_factory() as session:
        closed = await closed_entries(session)
    for i, (user_id, league) in enumerate(promoted, 1):
        text = PROMOTED.format(name=LEAGUES[league].name, income=round(LEAGUE_INCOME_STEP * league * 100), power=round(LEAGUE_POWER_STEP * league * 100))
        await notify(bot, user_id, text, reply_markup=country_menu(closed, league))
        if i % _PUSHES_PER_SECOND == 0:
            await asyncio.sleep(1)


async def league_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> None:
    while True:
        try:
            if await sweep_due(redis):
                promoted = await daily_sweep(session_factory)
                log.info("League sweep: promoted %d", len(promoted))
                await send_promotions(bot, session_factory, promoted)
        except Exception:
            log.exception("League sweep failed")
        await asyncio.sleep(LEAGUE_SWEEP_TICK_SECONDS)
