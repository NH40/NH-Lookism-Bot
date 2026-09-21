from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis


def make_redis_pool(redis_url: str) -> ConnectionPool:
    return ConnectionPool.from_url(redis_url, decode_responses=True, max_connections=50)


def make_redis(pool: ConnectionPool) -> Redis:
    return Redis(connection_pool=pool)
