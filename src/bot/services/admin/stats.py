"""Админка — статистика (сервис): агрегаты одним-двумя SQL на экран."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.battle_pass import BP_LEVEL_XP

_STARTED_AT = time.time()  # импорт модуля ≈ старт процесса бота


def _d(row) -> dict:
    return dict(row._mapping)


async def overview(session: AsyncSession) -> dict:
    row = (await session.execute(text("""
        SELECT count(*) AS total,
          count(*) FILTER (WHERE created_at >= date_trunc('day', now())) AS reg_today,
          count(*) FILTER (WHERE created_at >= now() - interval '7 days') AS reg_7d,
          count(*) FILTER (WHERE last_active_at >= now() - interval '1 day') AS online_24h,
          count(*) FILTER (WHERE last_active_at >= now() - interval '7 days') AS online_7d,
          count(*) FILTER (WHERE is_banned) AS banned,
          count(*) FILTER (WHERE created_at::date = (now() - interval '1 day')::date) AS d1_cohort,
          count(*) FILTER (WHERE created_at::date = (now() - interval '1 day')::date
                           AND last_active_at >= created_at + interval '1 day') AS d1_kept,
          count(*) FILTER (WHERE created_at::date = (now() - interval '7 days')::date) AS d7_cohort,
          count(*) FILTER (WHERE created_at::date = (now() - interval '7 days')::date
                           AND last_active_at >= created_at + interval '7 days') AS d7_kept,
          (SELECT count(*) FROM gangs) AS gangs
        FROM users WHERE id NOT BETWEEN 990000000 AND 990000999
    """))).one()
    return _d(row)


async def donate(session: AsyncSession) -> dict:
    row = (await session.execute(text("""
        SELECT COALESCE(sum(amount_rub), 0) AS total,
          COALESCE(sum(amount_rub) FILTER (WHERE created_at >= date_trunc('day', now())), 0) AS today,
          COALESCE(sum(amount_rub) FILTER (WHERE created_at >= now() - interval '7 days'), 0) AS d7,
          COALESCE(sum(amount_rub) FILTER (WHERE created_at >= now() - interval '30 days'), 0) AS d30,
          count(DISTINCT user_id) AS donors,
          (SELECT count(*) FROM donate_unlocks) AS unlocks,
          (SELECT count(*) FROM clan_donate_purchases) AS clan_purchases,
          (SELECT COALESCE(sum(donate_coins), 0) FROM users) AS circulation,
          (SELECT count(*) FROM battle_passes bp JOIN bp_seasons s ON s.id = bp.season_id
             WHERE bp.is_premium AND s.starts_at <= now() AND s.ends_at > now()) AS bp_premium
        FROM payments
    """))).one()
    top = (await session.execute(text("""
        SELECT p.user_id, u.username, sum(p.amount_rub) AS total
        FROM payments p LEFT JOIN users u ON u.id = p.user_id
        GROUP BY p.user_id, u.username ORDER BY total DESC LIMIT 10
    """))).all()
    return {**_d(row), "top": [tuple(r) for r in top]}


async def economy(session: AsyncSession) -> dict:
    res = (await session.execute(text("""
        SELECT COALESCE(sum(nh_coins),0) AS coins, COALESCE(sum(tickets_count),0) AS tickets,
          COALESCE(sum(dev_points),0) AS dev_pts, COALESCE(sum(path_points),0) AS path_pts,
          COALESCE(sum(path_fragments),0) AS path_fr, COALESCE(sum(technique_fragments),0) AS tech_fr,
          COALESCE(sum(genius_fragments),0) AS gen_fr, COALESCE(sum(blood_drops),0) AS blood,
          COALESCE(sum(donate_coins),0) AS donate
        FROM users WHERE id NOT BETWEEN 990000000 AND 990000999
    """))).one()
    extra = (await session.execute(text("""
        SELECT COALESCE(sum(e.quantity),0) FROM extras e WHERE e.user_id NOT BETWEEN 990000000 AND 990000999
    """))).scalar_one()
    biz = (await session.execute(text("SELECT type, count(*) FROM businesses GROUP BY type ORDER BY type"))).all()
    misc = (await session.execute(text(f"""
        SELECT (SELECT count(*) FROM districts WHERE owner_id IS NOT NULL) AS owned,
          (SELECT count(*) FROM districts WHERE owner_id IS NULL) AS bots,
          (SELECT count(*) FROM clans) AS clans,
          (SELECT COALESCE(avg(bp.xp / {int(BP_LEVEL_XP)}), 0) FROM battle_passes bp JOIN bp_seasons s ON s.id = bp.season_id
             WHERE s.starts_at <= now() AND s.ends_at > now()) AS bp_avg
    """))).one()
    return {"res": _d(res), "extras": int(extra), "biz": [tuple(r) for r in biz], **_d(misc)}


@dataclass
class ServerStats:
    cpu: float | None = None
    ram_used: int = 0
    ram_total: int = 0
    disk_used: int = 0
    disk_total: int = 0
    available: bool = True


def _read_server() -> ServerStats:
    try:
        import psutil
    except ImportError:
        return ServerStats(available=False)
    mem, disk = psutil.virtual_memory(), psutil.disk_usage("/")
    return ServerStats(psutil.cpu_percent(interval=None), mem.used, mem.total, disk.used, disk.total)


async def server(session: AsyncSession, redis) -> dict:
    stats = await asyncio.to_thread(_read_server)
    db_size = await session.scalar(text("SELECT pg_database_size(current_database())"))
    redis_mem = None
    try:
        redis_mem = (await redis.info("memory")).get("used_memory_human")
    except Exception:  # noqa: BLE001 — Redis недоступен: просто прочерк
        pass
    return {"srv": stats, "db_size": int(db_size or 0), "redis_mem": redis_mem, "uptime": int(time.time() - _STARTED_AT)}


async def series(session: AsyncSession, days: int) -> dict:
    """Ряды по дням для графиков админки (Mini App): регистрации и донат — за `days` дней,
    активные игроки — по журналу действий (он хранится `ACTIVITY_KEEP_DAYS`). Пустые дни — нули."""
    from bot.config.activity import ACTIVITY_KEEP_DAYS

    def rows(sql: str, n: int):
        return session.execute(text(sql), {"n": n})

    reg = await rows("""
        SELECT d::date, count(u.id) FROM generate_series(current_date - (:n - 1), current_date, interval '1 day') d
        LEFT JOIN users u ON u.created_at::date = d::date AND u.id NOT BETWEEN 990000000 AND 990000999
        GROUP BY 1 ORDER BY 1
    """, days)
    pay = await rows("""
        SELECT d::date, COALESCE(sum(p.amount_rub), 0) FROM generate_series(current_date - (:n - 1), current_date, interval '1 day') d
        LEFT JOIN payments p ON p.created_at::date = d::date
        GROUP BY 1 ORDER BY 1
    """, days)
    act_days = min(days, ACTIVITY_KEEP_DAYS)
    act = await rows("""
        SELECT d::date, count(DISTINCT a.user_id) FROM generate_series(current_date - (:n - 1), current_date, interval '1 day') d
        LEFT JOIN activity_log a ON a.created_at::date = d::date AND a.user_id NOT BETWEEN 990000000 AND 990000999
        GROUP BY 1 ORDER BY 1
    """, act_days)
    pack = lambda result: [{"day": d.isoformat(), "value": int(v or 0)} for d, v in result.all()]  # noqa: E731
    return {"registrations": pack(reg), "donate": pack(pay), "active": pack(act), "active_days": act_days}
