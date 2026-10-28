"""Фазы — банда -> круг -> кулак, переходы по захвату города/страны (репозиторий).

Все функции НЕ коммитят: проверка перехода — шаг той же транзакции, что и захват
района/города (правило 10), иначе игрок мог бы получить районы без фазы или наоборот.
"""
from __future__ import annotations

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.phase import PHASE_FIST, PHASE_GANG
from bot.db.models.business import Business
from bot.db.models.city import City
from bot.db.models.emperor_tax import EmperorTaxOverride
from bot.db.models.district import District
from bot.config.game import INFLUENCE_PER_DISTRICT
from bot.db.models.user import User


async def get_phase(session: AsyncSession, user_id: int) -> tuple[str, str | None] | None:
    """(фаза, страна) — свежим запросом, не из ORM-объекта вызывающего кода: объект мог
    быть загружен до захвата в этой же транзакции."""
    row = (await session.execute(select(User.phase, User.country_code).where(User.id == user_id))).one_or_none()
    return (row[0], row[1]) if row else None


async def count_not_owned_in_city(session: AsyncSession, city_id: int, user_id: int) -> int:
    return await session.scalar(
        select(func.count(District.id)).where(
            District.city_id == city_id, District.owner_id.is_distinct_from(user_id)
        )
    )


async def count_not_owned_in_country(session: AsyncSession, country_code: str, user_id: int) -> int:
    return await session.scalar(
        select(func.count(District.id))
        .join(City, City.id == District.city_id)
        .where(City.country_code == country_code, District.owner_id.is_distinct_from(user_id))
    )


async def promote(session: AsyncSession, user_id: int, from_phase: str, to_phase: str) -> bool:
    """`UPDATE ... WHERE phase = :из` (правило 1) — повторная проверка в параллельной
    транзакции не повысит дважды и не "перепрыгнет" фазу."""
    result = await session.execute(
        update(User).where(User.id == user_id, User.phase == from_phase).values(phase=to_phase)
    )
    return result.rowcount > 0


async def country_emperor(session: AsyncSession, country_code: str, *, exclude_user_id: int) -> int | None:
    """Действующий император страны (игрок в фазе кулака с этой страной), кроме себя."""
    return await session.scalar(
        select(User.id).where(
            User.country_code == country_code, User.phase == PHASE_FIST, User.id != exclude_user_id
        ).limit(1)
    )


async def crown(session: AsyncSession, user_id: int, country_code: str) -> None:
    """Коронация: фаза кулака, все города страны — его; районы освобождаются, здания на них
    уходят во «владения» (`holder_id`) — доход остаётся (пользователь 2026-10-01). НЕ коммитит."""
    await session.execute(update(User).where(User.id == user_id).values(phase=PHASE_FIST))
    # Влияние за районы — в копилку до их освобождения (+1 за район, `config/game.INFLUENCE_PER_DISTRICT`).
    await session.execute(
        update(User).where(User.id == user_id).values(
            influence_banked=User.influence_banked
            + select(func.count(District.id)).where(District.owner_id == user_id).scalar_subquery() * INFLUENCE_PER_DISTRICT
        )
    )
    await session.execute(update(City).where(City.country_code == country_code).values(emperor_id=user_id))
    await session.execute(
        update(Business)
        .where(Business.district_id.in_(select(District.id).where(District.owner_id == user_id)))
        .values(
            holder_id=user_id,
            origin_city_id=select(District.city_id).where(District.id == Business.district_id).scalar_subquery(),
            district_id=None,
        )
    )
    await session.execute(
        update(District).where(District.owner_id == user_id).values(owner_id=None, captured_at=None)
    )


async def demote_to_gang(session: AsyncSession, user_id: int) -> None:
    """Проигравший бой за трон: фаза банды, районы и бизнес (на районах и во владениях)
    теряются, города больше ему не платят. Армия, уники, прокачка, ресурсы — остаются
    (пользователь 2026-10-01). НЕ коммитит."""
    await session.execute(update(User).where(User.id == user_id).values(phase=PHASE_GANG))
    await session.execute(
        delete(Business).where(
            or_(
                Business.holder_id == user_id,
                Business.district_id.in_(select(District.id).where(District.owner_id == user_id)),
            )
        )
    )
    await session.execute(
        update(District).where(District.owner_id == user_id).values(owner_id=None, captured_at=None)
    )
    await session.execute(update(City).where(City.emperor_id == user_id).values(emperor_id=None))
    # Свергнутый император теряет и персональные налоги: вернётся на трон — настроит заново.
    await session.execute(delete(EmperorTaxOverride).where(EmperorTaxOverride.emperor_id == user_id))



async def foreign_holders(session: AsyncSession, country_code: str) -> list[tuple[int, int]]:
    """Чужие императоры, держащие города страны (отбитые в войнах императоров): (user_id, городов),
    крупнейший — первым (пользователь 2026-10-14: «бой с каждым по очереди»)."""
    count = func.count(City.id)
    rows = await session.execute(
        select(City.emperor_id, count)
        .join(User, User.id == City.emperor_id)
        .where(City.country_code == country_code, City.emperor_id.is_not(None), User.country_code != country_code)
        .group_by(City.emperor_id)
        .order_by(count.desc(), City.emperor_id)
    )
    return [(uid, int(n)) for uid, n in rows.all()]


async def release_cities(session: AsyncSession, country_code: str, emperor_id: int) -> list[tuple[int, str]]:
    """Освободить города страны у чужого императора. → [(city_id, название)]. НЕ коммитит."""
    rows = await session.execute(
        update(City)
        .where(City.country_code == country_code, City.emperor_id == emperor_id)
        .values(emperor_id=None)
        .returning(City.id, City.name)
    )
    return [(cid, name) for cid, name in rows.all()]


async def count_cities_of(session: AsyncSession, emperor_id: int) -> int:
    return int(await session.scalar(select(func.count(City.id)).where(City.emperor_id == emperor_id)) or 0)


async def transfer_holdings(
    session: AsyncSession, from_id: int, to_id: int, city_ids: list[int], cities_before: int, *, everything: bool = False
) -> int:
    """Владения проигравшего императора переходят победителю (пользователь 2026-10-14):
    здания, пришедшие из потерянных городов (`origin_city_id`), и доля старых владений без
    города — пропорционально `len(city_ids) / cities_before`. `everything` — окончательное
    поражение: уходит всё. → сколько зданий перешло. НЕ коммитит."""
    if everything:
        result = await session.execute(update(Business).where(Business.holder_id == from_id).values(holder_id=to_id))
        return result.rowcount or 0
    moved = 0
    if city_ids:
        result = await session.execute(
            update(Business).where(Business.holder_id == from_id, Business.origin_city_id.in_(city_ids)).values(holder_id=to_id)
        )
        moved += result.rowcount or 0
    legacy = int(await session.scalar(
        select(func.count(Business.id)).where(Business.holder_id == from_id, Business.origin_city_id.is_(None))
    ) or 0)
    share = round(legacy * len(city_ids) / cities_before) if cities_before > 0 else 0
    if share > 0:
        ids = select(Business.id).where(Business.holder_id == from_id, Business.origin_city_id.is_(None)).order_by(func.random()).limit(share)
        result = await session.execute(update(Business).where(Business.id.in_(ids)).values(holder_id=to_id))
        moved += result.rowcount or 0
    return moved
