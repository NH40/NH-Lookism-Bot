"""Общие зависимости API: Redis (локи действий и КД — те же ключи, что у бота)."""
from __future__ import annotations

from redis.asyncio import Redis

from bot.cache.redis_client import make_redis, make_redis_pool
from bot.config.settings import get_settings

_pool = make_redis_pool(get_settings().redis_url)


async def get_redis() -> Redis:
    return make_redis(_pool)
