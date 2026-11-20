"""Живая карта страны (2026-11-20, «карта с нуля»): силуэт страны с городами, короны императоров,
цвета кланов, идущие онлайн-бои и лента захватов. Всё читается из уже существующих таблиц и Redis
арены — без новых записей и хуков: лента = свежие `districts.captured_at`, бои = `arena:live`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FEED_HOURS = 24
FEED_LIMIT = 30
FRESH_SECONDS = 15 * 60  # район «только что захвачен» — подсветка на карте города


async def _clans(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = await session.execute(text("SELECT id, name FROM clans WHERE id = ANY(:ids)"), {"ids": list(ids)})
    return {i: n for i, n in rows.all()}


async def live_battles(session: AsyncSession, redis: Redis, country_code: str) -> list[dict]:
    """Идущие онлайн-бои страны: {city_id, district_id, kind, a, d, round}."""
    from bot.services.arena.arena import LIVE_SET

    ids = list(await redis.smembers(LIVE_SET))[:200]
    if not ids:
        return []
    raw = await redis.mget([f"arena:{i.decode() if isinstance(i, bytes) else i}" for i in ids])
    states = [json.loads(r) for r in raw if r]
    dist_ids = {s["meta"]["district_id"] for s in states if "district_id" in s.get("meta", {})}
    ch_ids = {s["meta"]["challenge_id"] for s in states if "challenge_id" in s.get("meta", {})}
    d2c: dict[int, int] = {}
    if dist_ids:
        d2c = dict((await session.execute(text("SELECT id, city_id FROM districts WHERE id = ANY(:i)"), {"i": list(dist_ids)})).all())
    ch: dict[int, tuple[int | None, int | None]] = {}
    if ch_ids:
        for cid, did, city in (await session.execute(text(
            "SELECT c.id, c.district_id, coalesce(c.city_id, d.city_id) FROM district_challenges c "
            "LEFT JOIN districts d ON d.id = c.district_id WHERE c.id = ANY(:i)"), {"i": list(ch_ids)})).all():
            ch[cid] = (did, city)
    cities = {c for c in d2c.values()} | {c for _, c in ch.values() if c} | {s["meta"]["city_id"] for s in states if "city_id" in s.get("meta", {})}
    in_country = set()
    if cities:
        in_country = {r[0] for r in (await session.execute(text(
            "SELECT id FROM cities WHERE id = ANY(:i) AND country_code = :cc"), {"i": list(cities), "cc": country_code})).all()}
    out = []
    for s in states:
        meta = s.get("meta", {})
        did = meta.get("district_id")
        city = d2c.get(did) if did else meta.get("city_id")
        if "challenge_id" in meta:
            did, city = ch.get(meta["challenge_id"], (None, None))
        if city in in_country and s.get("status") == "live":
            out.append({"id": s["id"], "city_id": city, "district_id": did, "kind": s["kind"],
                        "a": s["a"]["name"], "d": s["d"]["name"], "round": s["round"]})
    return out


async def country_overview(session: AsyncSession, redis: Redis, country_code: str, user_id: int) -> dict:
    rows = (await session.execute(text(
        """SELECT c.id, c.name, c.district_count, c.emperor_id, ge.name, me.clan_id,
                  count(d.id) FILTER (WHERE d.owner_id IS NULL), count(DISTINCT d.owner_id),
                  count(d.id) FILTER (WHERE d.owner_id = :u),
                  (SELECT count(*) FROM users u WHERE u.city_id = c.id)
           FROM cities c LEFT JOIN districts d ON d.city_id = c.id
           LEFT JOIN gangs ge ON ge.user_id = c.emperor_id LEFT JOIN clan_members me ON me.user_id = c.emperor_id
           WHERE c.country_code = :cc GROUP BY c.id, ge.name, me.clan_id ORDER BY c.id"""),
        {"cc": country_code, "u": user_id})).all()
    top = {r[0]: r[1:] for r in (await session.execute(text(
        """SELECT DISTINCT ON (d.city_id) d.city_id, g.name, m.clan_id, count(*) AS n
           FROM districts d JOIN cities c ON c.id = d.city_id LEFT JOIN gangs g ON g.user_id = d.owner_id
           LEFT JOIN clan_members m ON m.user_id = d.owner_id
           WHERE c.country_code = :cc AND d.owner_id IS NOT NULL
           GROUP BY d.city_id, d.owner_id, g.name, m.clan_id ORDER BY d.city_id, n DESC"""), {"cc": country_code})).all()}
    feed = (await session.execute(text(
        """SELECT d.captured_at, d.number, c.id, c.name, g.name, m.clan_id FROM districts d JOIN cities c ON c.id = d.city_id
           LEFT JOIN gangs g ON g.user_id = d.owner_id LEFT JOIN clan_members m ON m.user_id = d.owner_id
           WHERE c.country_code = :cc AND d.owner_id IS NOT NULL AND d.captured_at > now() - make_interval(hours => :h)
           ORDER BY d.captured_at DESC LIMIT :n"""), {"cc": country_code, "h": FEED_HOURS, "n": FEED_LIMIT})).all()
    my_city, my_clan = (await session.execute(text(
        "SELECT u.city_id, m.clan_id FROM users u LEFT JOIN clan_members m ON m.user_id = u.id WHERE u.id = :u"), {"u": user_id})).one()
    clan_ids = {r[5] for r in rows if r[5]} | {t[1] for t in top.values() if t[1]} | {f[5] for f in feed if f[5]}
    clans = await _clans(session, clan_ids)
    now = datetime.now(timezone.utc)
    cities = []
    for cid, name, dcount, emp_id, emp_name, emp_clan, bots, owners, mine, pop in rows:
        t = top.get(cid)
        cities.append({
            "id": cid, "name": name, "districts": dcount, "bots": bots, "owners": owners, "mine": mine, "population": pop,
            "emperor": emp_name if emp_id else None, "emperor_clan": emp_clan,
            "top": t[0] if t else None, "top_share": round(t[2] / dcount, 2) if t else 0,
            "clan": emp_clan or (t[1] if t else None),
        })
    return {
        "country": country_code, "my_city": my_city, "my_clan": my_clan,
        "clans": {str(k): v for k, v in clans.items()},
        "cities": cities,
        "battles": await live_battles(session, redis, country_code),
        "feed": [{"ago": int((now - at).total_seconds()), "number": num, "city_id": cid, "city": cname, "who": who or "—", "clan": clan}
                 for at, num, cid, cname, who, clan in feed],
    }


async def city_districts(session: AsyncSession, city_id: int, user_id: int) -> dict:
    """Районы любого города страны (просмотр): владелец, его клан, свежий захват."""
    city = (await session.execute(text(
        "SELECT c.name, c.district_count, c.country_code, g.name FROM cities c LEFT JOIN gangs g ON g.user_id = c.emperor_id WHERE c.id = :c"),
        {"c": city_id})).one_or_none()
    if city is None:
        return {}
    rows = (await session.execute(text(
        """SELECT d.id, d.number, d.owner_id, g.name, m.clan_id, extract(epoch FROM now() - d.captured_at)::int
           FROM districts d LEFT JOIN gangs g ON g.user_id = d.owner_id LEFT JOIN clan_members m ON m.user_id = d.owner_id
           WHERE d.city_id = :c ORDER BY d.number"""), {"c": city_id})).all()
    clans = await _clans(session, {r[4] for r in rows if r[4]})
    return {
        "city_id": city_id, "city": city[0], "count": city[1], "country": city[2], "emperor": city[3],
        "clans": {str(k): v for k, v in clans.items()},
        "districts": [{"id": i, "number": n, "kind": "mine" if o == user_id else "bot" if o is None else "player",
                       "owner": name, "owner_id": o, "clan": clan, "fresh": ago is not None and ago < FRESH_SECONDS}
                      for i, n, o, name, clan, ago in rows],
    }
