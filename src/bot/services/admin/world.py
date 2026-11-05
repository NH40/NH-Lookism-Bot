"""Админка «Районы, города, императоры» (сервис). Все мутации пишут аудит в ТОЙ ЖЕ транзакции
и коммитят один раз в конце."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, text, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin.world import (
    AUDIT_W_CANCEL_CHALLENGES, AUDIT_W_CANCEL_WAR, AUDIT_W_COUNTRY_BATTLES, AUDIT_W_COUNTRY_ENTRY, AUDIT_W_COUNTRY_KICK, AUDIT_W_DEL_EMP, AUDIT_W_RESET, AUDIT_W_SET_EMP,
    AUDIT_W_SET_OWNER, CHALLENGE_CANCELLED, RESOLUTION_ADMIN, SEARCH_LIMIT, WAR_CANCELLED,
)
from bot.constant.district import CHALLENGE_PENDING
from bot.constant.empire import WAR_PENDING
from bot.constant.phase import PHASE_GANG
from bot.db.models.business import Business
from bot.db.models.country import Country
from bot.db.models.emperor_tax import EmperorTaxOverride
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
    flags = {r[0]: (r[1], r[2]) for r in await session.execute(select(Country.code, Country.entry_closed, Country.battles_closed))}
    players = dict((await session.execute(
        select(User.country_code, func.count()).where(User.country_code.is_not(None)).group_by(User.country_code)
    )).all())
    out = []
    for c in COUNTRIES:
        r = by_code.get(c.code)
        if r is None:
            continue
        out.append({
            "code": c.code, "name": c.name, "cities": r[1], "owned": r[2], "bots": r[3],
            "entry_closed": flags.get(c.code, (False, False))[0], "battles_closed": flags.get(c.code, (False, False))[1],
            "players": players.get(c.code, 0),
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


async def set_country_entry(session: AsyncSession, admin_id: int, code: str, closed: bool) -> bool:
    """Закрыть/открыть вход в страну. Игроки внутри не затрагиваются. Коммитит. → есть ли страна."""
    result = await session.execute(update(Country).where(Country.code == code).values(entry_closed=closed))
    if not result.rowcount:
        return False
    await audit.log(session, admin_id, AUDIT_W_COUNTRY_ENTRY, None, {"country": code, "closed": closed})
    await session.commit()
    return True


_COUNTRY_DISTRICTS = "SELECT d.id FROM districts d JOIN cities c ON c.id = d.city_id WHERE c.country_code = :cc"
_COUNTRY_CITIES = "SELECT id FROM cities WHERE country_code = :cc"


async def _cancel_country_fights(session: AsyncSession, code: str) -> tuple[int, int]:
    """Отменить висящие вызовы в стране и войны её игроков: иначе они дозрели бы до боя. НЕ коммитит."""
    challenges = await session.execute(text(f"""
        UPDATE district_challenges SET status = :cancelled, resolution = :admin, resolved_at = now()
        WHERE status = :pending AND (
            city_id IN ({_COUNTRY_CITIES}) OR district_id IN ({_COUNTRY_DISTRICTS})
            OR attacker_id IN (SELECT id FROM users WHERE country_code = :cc)
            OR defender_id IN (SELECT id FROM users WHERE country_code = :cc)
        )
    """), {"cc": code, "cancelled": CHALLENGE_CANCELLED, "admin": RESOLUTION_ADMIN, "pending": CHALLENGE_PENDING})
    wars = await session.execute(text("""
        UPDATE emperor_wars SET status = :cancelled, resolution = :admin, resolved_at = now()
        WHERE status = :pending AND (
            attacker_id IN (SELECT id FROM users WHERE country_code = :cc)
            OR defender_id IN (SELECT id FROM users WHERE country_code = :cc)
        )
    """), {"cc": code, "cancelled": WAR_CANCELLED, "admin": RESOLUTION_ADMIN, "pending": WAR_PENDING})
    return challenges.rowcount or 0, wars.rowcount or 0


async def set_country_battles(session: AsyncSession, admin_id: int, code: str, closed: bool) -> tuple[int, int] | None:
    """Запретить/разрешить бои в стране. При запрете висящие вызовы и войны отменяются. Коммитит.
    → (отменено вызовов, войн) или None, если страны нет."""
    result = await session.execute(update(Country).where(Country.code == code).values(battles_closed=closed))
    if not result.rowcount:
        return None
    cancelled = await _cancel_country_fights(session, code) if closed else (0, 0)
    await audit.log(session, admin_id, AUDIT_W_COUNTRY_BATTLES, None, {"country": code, "closed": closed, "challenges": cancelled[0], "wars": cancelled[1]})
    await session.commit()
    return cancelled


async def kick_country(session: AsyncSession, admin_id: int, code: str) -> list[int]:
    """Выселить всех игроков страны. Одна транзакция, всё SQL-запросами (правило 3).

    Игрок сохраняет армию, уников, ресурсы и развитие. Здания на районах становятся владениями (доход
    остаётся, как при коронации). Районы страны уходят ботам, города теряют императоров, сами выселенные
    теряют и чужие города, и персональные налоги. Фаза — банда, как у свергнутого императора: иначе в новой
    стране оказался бы второй император. Дальше игрок выбирает страну заново через /start. Коммитит.
    → id выселенных (для уведомлений)."""
    kicked = list((await session.scalars(
        select(User.id).where(User.country_code == code).order_by(User.id).with_for_update()
    )).all())
    owners = list((await session.scalars(text(f"SELECT DISTINCT owner_id FROM districts WHERE owner_id IS NOT NULL AND id IN ({_COUNTRY_DISTRICTS})"), {"cc": code})).all())
    to_accrue = sorted(set(kicked) | set(owners))
    if to_accrue:
        await accrue_many(session, to_accrue)  # доход до этой секунды — по старому набору зданий
    challenges, wars = await _cancel_country_fights(session, code)
    await session.execute(text(f"""
        UPDATE businesses b SET holder_id = d.owner_id, origin_city_id = d.city_id, district_id = NULL
        FROM districts d WHERE b.district_id = d.id AND d.owner_id IS NOT NULL AND d.id IN ({_COUNTRY_DISTRICTS})
    """), {"cc": code})
    await session.execute(text(f"UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE owner_id IS NOT NULL AND id IN ({_COUNTRY_DISTRICTS})"), {"cc": code})
    await session.execute(update(City).where(City.country_code == code).values(emperor_id=None))
    if kicked:
        await session.execute(update(City).where(City.emperor_id.in_(kicked)).values(emperor_id=None))
        await session.execute(delete(EmperorTaxOverride).where(EmperorTaxOverride.emperor_id.in_(kicked)))
    await session.execute(
        update(User).where(User.country_code == code).values(phase=PHASE_GANG, country_code=None, city_id=None)
    )
    await audit.log(session, admin_id, AUDIT_W_COUNTRY_KICK, None, {"country": code, "players": len(kicked), "challenges": challenges, "wars": wars})
    await session.commit()
    return kicked


async def send_kick_notices(bot, user_ids: list[int], country_name: str) -> None:
    """Сообщить выселенным. Шлётся всем без учёта настроек: без этого игрок не поймёт, что случилось.
    Фоновая задача, best-effort: заблокировавшие бота пропускаются, темп — в лимитах Telegram."""
    import asyncio

    from bot.texts.country import KICKED_NOTICE

    for i, user_id in enumerate(user_ids, 1):
        try:
            await bot.send_message(user_id, KICKED_NOTICE.format(name=country_name))
        except Exception:  # noqa: BLE001 — заблокировал бота, удалён и т.п.
            pass
        if i % 25 == 0:
            await asyncio.sleep(1)
