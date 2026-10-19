"""Админка «Районы, города, императоры» (сервис). Все мутации пишут аудит в ТОЙ ЖЕ транзакции
и коммитят один раз в конце."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin.world import (
    AUDIT_W_CANCEL_CHALLENGES, AUDIT_W_CANCEL_WAR, AUDIT_W_DEL_EMP, AUDIT_W_RESET, AUDIT_W_SET_EMP,
    AUDIT_W_SET_OWNER, CHALLENGE_CANCELLED, RESOLUTION_ADMIN, SEARCH_LIMIT, WAR_CANCELLED,
)
from bot.constant.district import CHALLENGE_PENDING
from bot.constant.empire import WAR_PENDING
from bot.db.models.business import Business
from bot.db.models.city import City
from bot.db.models.district import District
from bot.db.models.district_challenge import DistrictChallenge
from bot.db.models.emperor_war import EmperorWar
from bot.db.models.user import User
from bot.db.repositories import district as district_repo
from bot.services.admin import audit
from bot.services.business import accrue_many


@dataclass(frozen=True, slots=True)
class CityView:
    city: City
    emperor: User | None
    districts: list  # DistrictRow
    pending_challenges: int


def player_label(user: User | None) -> str:
    if user is None:
        return "—"
    return f"@{user.username}" if user.username else f"id{user.id}"


async def find_cities(session: AsyncSession, query: str) -> list[City]:
    pattern = f"%{query.strip().lower()}%"
    rows = await session.scalars(
        select(City).where(func.lower(City.name).like(pattern)).order_by(City.name).limit(SEARCH_LIMIT)
    )
    return list(rows.all())


async def _pending_for_city(session: AsyncSession, city_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(DistrictChallenge).where(
            DistrictChallenge.status == CHALLENGE_PENDING,
            (DistrictChallenge.city_id == city_id)
            | DistrictChallenge.district_id.in_(select(District.id).where(District.city_id == city_id)),
        )
    ) or 0


async def city_view(session: AsyncSession, city_id: int) -> CityView | None:
    city = await session.get(City, city_id)
    if city is None:
        return None
    emperor = await session.get(User, city.emperor_id) if city.emperor_id else None
    return CityView(city, emperor, await district_repo.list_by_city(session, city_id), await _pending_for_city(session, city_id))


async def district_pending(session: AsyncSession, district_id: int) -> DistrictChallenge | None:
    return await session.scalar(
        select(DistrictChallenge).where(
            DistrictChallenge.district_id == district_id, DistrictChallenge.status == CHALLENGE_PENDING
        )
    )


async def set_district_owner(session: AsyncSession, admin_id: int, district_id: int, new_owner: User) -> str:
    """→ "ok" | "same" | "stale". Доход бизнесов начисляется обеим сторонам по старому набору."""
    row = await session.scalar(select(District).where(District.id == district_id).with_for_update())
    if row is None:
        return "stale"
    if row.owner_id == new_owner.id:
        return "same"
    old = row.owner_id
    await accrue_many(session, [u for u in (old, new_owner.id) if u is not None])
    row.owner_id, row.captured_at = new_owner.id, func.now()
    await audit.log(session, admin_id, AUDIT_W_SET_OWNER, new_owner.id, {"district_id": district_id, "city_id": row.city_id, "number": row.number, "old_owner": old})
    await session.commit()
    return "ok"


async def reset_district(session: AsyncSession, admin_id: int, district_id: int) -> str:
    """Район → ботам; бизнесы на нём уходят во «владения» прежнего владельца (как при коронации)."""
    row = await session.scalar(select(District).where(District.id == district_id).with_for_update())
    if row is None or row.owner_id is None:
        return "bots" if row is not None else "stale"
    old = row.owner_id
    await accrue_many(session, [old])
    await session.execute(
        update(Business).where(Business.district_id == district_id).values(holder_id=old, district_id=None)
    )
    row.owner_id, row.captured_at = None, None
    await audit.log(session, admin_id, AUDIT_W_RESET, old, {"district_id": district_id, "city_id": row.city_id, "number": row.number})
    await session.commit()
    return "ok"


async def set_emperor(session: AsyncSession, admin_id: int, city_id: int, user: User) -> bool:
    city = await session.scalar(select(City).where(City.id == city_id).with_for_update())
    if city is None:
        return False
    old = city.emperor_id
    city.emperor_id = user.id
    await audit.log(session, admin_id, AUDIT_W_SET_EMP, user.id, {"city_id": city_id, "old_emperor": old})
    await session.commit()
    return True


async def remove_emperor(session: AsyncSession, admin_id: int, city_id: int) -> bool:
    city = await session.scalar(select(City).where(City.id == city_id).with_for_update())
    if city is None or city.emperor_id is None:
        return False
    old = city.emperor_id
    city.emperor_id = None
    await audit.log(session, admin_id, AUDIT_W_DEL_EMP, old, {"city_id": city_id})
    await session.commit()
    return True


async def cancel_city_challenges(session: AsyncSession, admin_id: int, city_id: int) -> int:
    result = await session.execute(
        update(DistrictChallenge)
        .where(
            DistrictChallenge.status == CHALLENGE_PENDING,
            (DistrictChallenge.city_id == city_id)
            | DistrictChallenge.district_id.in_(select(District.id).where(District.city_id == city_id)),
        )
        .values(status=CHALLENGE_CANCELLED, resolution=RESOLUTION_ADMIN, resolved_at=func.now())
    )
    count = result.rowcount or 0
    await audit.log(session, admin_id, AUDIT_W_CANCEL_CHALLENGES, None, {"city_id": city_id, "count": count})
    await session.commit()
    return count


async def pending_wars_of(session: AsyncSession, emperor_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(EmperorWar).where(
            EmperorWar.status == WAR_PENDING, (EmperorWar.attacker_id == emperor_id) | (EmperorWar.defender_id == emperor_id)
        )
    ) or 0


async def cancel_emperor_wars(session: AsyncSession, admin_id: int, emperor_id: int) -> int:
    result = await session.execute(
        update(EmperorWar)
        .where(EmperorWar.status == WAR_PENDING, (EmperorWar.attacker_id == emperor_id) | (EmperorWar.defender_id == emperor_id))
        .values(status=WAR_CANCELLED, resolution=RESOLUTION_ADMIN, resolved_at=func.now())
    )
    count = result.rowcount or 0
    await audit.log(session, admin_id, AUDIT_W_CANCEL_WAR, emperor_id, {"count": count})
    await session.commit()
    return count


async def countries_overview(session: AsyncSession) -> list[dict]:
    """Страны для раздела «Мир»: городов, районов у игроков/ботов, император (один запрос)."""
    from bot.config.country import COUNTRIES

    rows = (await session.execute(text("""
        SELECT c.country_code, count(DISTINCT c.id),
               count(d.id) FILTER (WHERE d.owner_id IS NOT NULL), count(d.id) FILTER (WHERE d.owner_id IS NULL),
               (SELECT u.username FROM cities c2 JOIN users u ON u.id = c2.emperor_id
                 WHERE c2.country_code = c.country_code GROUP BY u.id, u.username ORDER BY count(*) DESC LIMIT 1),
               (SELECT c3.emperor_id FROM cities c3 WHERE c3.country_code = c.country_code AND c3.emperor_id IS NOT NULL
                 GROUP BY c3.emperor_id ORDER BY count(*) DESC LIMIT 1)
        FROM cities c LEFT JOIN districts d ON d.city_id = c.id
        GROUP BY c.country_code
    """))).all()
    by_code = {r[0]: r for r in rows}
    out = []
    for c in COUNTRIES:
        r = by_code.get(c.code)
        if r is None:
            continue
        out.append({
            "code": c.code, "name": c.name, "cities": r[1], "owned": r[2], "bots": r[3],
            "emperor": {"id": r[5], "label": f"@{r[4]}" if r[4] else f"id{r[5]}"} if r[5] else None,
        })
    return out


async def country_cities(session: AsyncSession, country_code: str) -> list[dict]:
    """Города страны: император, районов всего/у ботов, сколько разных владельцев."""
    rows = (await session.execute(text("""
        SELECT c.id, c.name, c.emperor_id, u.username, count(d.id), count(d.id) FILTER (WHERE d.owner_id IS NULL),
               count(DISTINCT d.owner_id)
        FROM cities c LEFT JOIN districts d ON d.city_id = c.id LEFT JOIN users u ON u.id = c.emperor_id
        WHERE c.country_code = :cc GROUP BY c.id, c.name, c.emperor_id, u.username ORDER BY c.name
    """), {"cc": country_code})).all()
    return [
        {
            "id": cid, "name": name, "districts": total, "bots": bots, "owners": owners,
            "emperor": {"id": eid, "label": f"@{uname}" if uname else f"id{eid}"} if eid else None,
        }
        for cid, name, eid, uname, total, bots, owners in rows
    ]
