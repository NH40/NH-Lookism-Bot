"""Расширенная разведка (пользователь 2026-11-20): не только игроки — кланы, города, страны и население.

Глубина отчёта — уровень разведки игрока (`EconomyMods.scout`, 0–3) + 1 за «разведывательный» путь или технику
(Сенсорика, Предвидение, Ниндзюцу, Невидимые атаки), максимум 4:
0 — общие сведения (размер, владелец/император, население), числа мощи округлены до порядка;
1 — точные суммы мощи и казны; 2 — топ сильнейших (по 5); 3 — оборона (лагеря защиты, рота клана);
4 — всё, плюс доля активных за сутки. Всё по кэшу мощи (`army_power_cache`) — одним-двумя запросами.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SCOUT_PATHS = frozenset({"sensory", "foresight"})
SCOUT_TECHS = frozenset({"ninjutsu", "invisible"})
WORLD_SCOUT_COOLDOWN = 30  # секунд между отчётами (нагрузка на БД)


class WorldScoutError(Exception):
    def __init__(self, code: str, value: int = 0) -> None:
        super().__init__(code)
        self.code, self.value = code, value


@dataclass(frozen=True, slots=True)
class WorldReport:
    kind: str  # clan / city / country
    title: str
    level: int
    lines: list[tuple[str, str]] = field(default_factory=list)  # (подпись, значение)
    top: list[tuple[str, str]] = field(default_factory=list)  # (имя, мощь)


def _fmt(n: int | None, level: int) -> str:
    from bot.utils.formatting import format_number

    n = int(n or 0)
    if level >= 1 or n < 1000:
        return format_number(n)
    digits = len(str(n))
    return f"~{format_number(round(n, -(digits - 2)))}"


async def scout_level(session: AsyncSession, user_id: int) -> int:
    from bot.db.repositories import build as build_repo
    from bot.services.intel.intel import get_access

    base = min(3, (await get_access(session, user_id)).scout)
    row = await build_repo.get_row(session, user_id)
    bonus = bool(row and ({row.path, row.path2} & SCOUT_PATHS or row.technique in SCOUT_TECHS))
    return min(4, base + bonus)


async def _cooldown(redis: Redis, user_id: int) -> None:
    key = f"intel:world:{user_id}"
    if not await redis.set(key, "1", nx=True, ex=WORLD_SCOUT_COOLDOWN):
        raise WorldScoutError("cooldown", max(1, await redis.ttl(key)))


async def scout_clan(session: AsyncSession, redis: Redis, user_id: int, name: str) -> WorldReport:
    lvl = await scout_level(session, user_id)
    row = (await session.execute(text(
        """SELECT c.id, c.name, c.lands, c.treasury, c.donate_level, c.power_cache, g.name, count(m.user_id)
           FROM clans c LEFT JOIN gangs g ON g.user_id = c.owner_id LEFT JOIN clan_members m ON m.clan_id = c.id
           WHERE lower(c.name) = lower(:n) GROUP BY c.id, g.name"""), {"n": name.strip()})).one_or_none()
    if row is None:
        raise WorldScoutError("not_found")
    await _cooldown(redis, user_id)
    cid, cname, lands, treasury, dlvl, power, owner, members = row
    members_power = await session.scalar(text(
        "SELECT coalesce(sum(u.army_power_cache),0) FROM clan_members m JOIN users u ON u.id = m.user_id WHERE m.clan_id = :c"), {"c": cid})
    lines = [("Владелец", owner or "—"), ("Участников", str(members)), ("Земли", str(lands)), ("Уровень", str(dlvl)),
             ("Мощь участников", _fmt(members_power, lvl)), ("Казна", _fmt(treasury, lvl))]
    if lvl >= 3:
        lines.append(("Мощь клана (рота и постройки)", _fmt(power, lvl)))
    if lvl >= 4:
        active = await session.scalar(text("""SELECT count(*) FROM clan_members m JOIN users u ON u.id = m.user_id
            WHERE m.clan_id = :c AND u.last_active_at > now() - interval '1 day'"""), {"c": cid})
        lines.append(("Активны за сутки", f"{active} из {members}"))
    top = []
    if lvl >= 2:
        top = [(n or "—", _fmt(p, lvl)) for n, p in (await session.execute(text(
            """SELECT g.name, u.army_power_cache FROM clan_members m JOIN users u ON u.id = m.user_id LEFT JOIN gangs g ON g.user_id = u.id
               WHERE m.clan_id = :c ORDER BY u.army_power_cache DESC LIMIT 5"""), {"c": cid})).all()]
    return WorldReport("clan", f"Клан «{cname}»", lvl, lines, top)


async def scout_city(session: AsyncSession, redis: Redis, user_id: int, city_id: int) -> WorldReport:
    lvl = await scout_level(session, user_id)
    row = (await session.execute(text(
        """SELECT c.name, c.district_count, g.name, c.country_code FROM cities c LEFT JOIN gangs g ON g.user_id = c.emperor_id
           WHERE c.id = :c"""), {"c": city_id})).one_or_none()
    if row is None:
        raise WorldScoutError("not_found")
    await _cooldown(redis, user_id)
    cname, dcount, emperor, code = row
    owners = (await session.execute(text(
        """SELECT d.owner_id, g.name, count(*) AS n, max(u.army_power_cache) FROM districts d LEFT JOIN users u ON u.id = d.owner_id
           LEFT JOIN gangs g ON g.user_id = d.owner_id WHERE d.city_id = :c GROUP BY d.owner_id, g.name ORDER BY n DESC"""), {"c": city_id})).all()
    bots = next((n for o, _, n, _ in owners if o is None), 0)
    population, pop_power = (await session.execute(text(
        "SELECT count(*), coalesce(sum(army_power_cache),0) FROM users WHERE city_id = :c"), {"c": city_id})).one()
    lines = [("Император", emperor or "—"), ("Районов", f"{dcount} (у ботов {bots})"), ("Население", str(population)),
             ("Мощь жителей", _fmt(pop_power, lvl)), ("Владельцев районов", str(sum(1 for o, *_ in owners if o)))]
    if lvl >= 1:
        buildings = await session.scalar(text("SELECT count(*) FROM businesses b JOIN districts d ON d.id = b.district_id WHERE d.city_id = :c"), {"c": city_id})
        lines.append(("Зданий в городе", str(buildings)))
    if lvl >= 3:
        defense = await session.scalar(text("""SELECT coalesce(sum(e.quantity),0) FROM extras e WHERE e.camp = 'defense'
            AND e.user_id IN (SELECT DISTINCT owner_id FROM districts WHERE city_id = :c AND owner_id IS NOT NULL)"""), {"c": city_id})
        lines.append(("Статистов в обороне у владельцев", _fmt(defense, lvl)))
    top = [(n or "—", f"{k} р-нов · {_fmt(p, lvl)}") for o, n, k, p in owners if o][: 5 if lvl >= 2 else 0]
    return WorldReport("city", f"Город {cname}", lvl, lines, top)


async def scout_country(session: AsyncSession, redis: Redis, user_id: int, code: str) -> WorldReport:
    from bot.config.country import COUNTRY_BY_CODE

    lvl = await scout_level(session, user_id)
    country = COUNTRY_BY_CODE.get(code)
    if country is None:
        raise WorldScoutError("not_found")
    await _cooldown(redis, user_id)
    cities, emperors = (await session.execute(text(
        "SELECT count(*), count(DISTINCT emperor_id) FROM cities WHERE country_code = :k"), {"k": code})).one()
    population, power, holders = (await session.execute(text(
        """SELECT count(*), coalesce(sum(army_power_cache),0),
                  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM districts d WHERE d.owner_id = users.id))
           FROM users WHERE country_code = :k"""), {"k": code})).one()
    lines = [("Городов", str(cities)), ("Императоров", str(emperors)), ("Население", str(population)),
             ("С районами", str(holders)), ("Мощь жителей", _fmt(power, lvl))]
    if lvl >= 4:
        active = await session.scalar(text("SELECT count(*) FROM users WHERE country_code = :k AND last_active_at > now() - interval '1 day'"), {"k": code})
        lines.append(("Активны за сутки", str(active)))
    top = []
    if lvl >= 2:
        top = [(n or "—", _fmt(p, lvl)) for n, p in (await session.execute(text(
            """SELECT g.name, u.army_power_cache FROM users u LEFT JOIN gangs g ON g.user_id = u.id
               WHERE u.country_code = :k ORDER BY u.army_power_cache DESC LIMIT 5"""), {"k": code})).all()]
    return WorldReport("country", f"Страна {country.name}", lvl, lines, top)


ERRORS = {"not_found": "Не найдено.", "cooldown": "Разведка ещё готовится — {value} с."}
