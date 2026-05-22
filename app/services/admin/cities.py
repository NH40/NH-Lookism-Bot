import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User


class AdminCitiesMixin:

    async def give_king_city(self, session: AsyncSession, user: User) -> dict:
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo

        sector = user.sector or "Н"

        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase.in_(["gang", "king"]),
                City.total_districts == 16,
            ).order_by(City.id)
        )
        all_cities = result.scalars().all()

        target_city = None
        for city in all_cities:
            my_count = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_count == 0:
                target_city = city
                break

        if not target_city:
            from app.data.cities import CITY_NAMES_BY_SECTOR
            names = CITY_NAMES_BY_SECTOR.get(sector, [])
            used_names = {c.name for c in all_cities}
            available = [n for n in names if n not in used_names]
            name = random.choice(available) if available else f"Адм-{sector}-{len(all_cities)+1}"
            target_city = City(
                sector=sector, phase="king", type_id=3, name=name,
                total_districts=16, captured_districts=0,
                is_fully_captured=False, district_power_multiplier=1.0,
            )
            session.add(target_city)
            await session.flush()

        await city_repo.init_city_districts(session, target_city)
        await session.flush()

        districts_r = await session.execute(
            select(District).where(District.city_id == target_city.id)
        )
        districts = districts_r.scalars().all()
        for d in districts:
            d.owner_id = user.id
            d.is_captured = True

        target_city.captured_districts = len(districts)
        target_city.owner_id = user.id
        target_city.is_fully_captured = True

        cities_r = await session.execute(
            select(District.city_id)
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                City.phase != "fist",
            ).distinct()
        )
        user.king_cities_count = len(cities_r.scalars().all())
        await session.flush()
        return {"ok": True, "cities_count": user.king_cities_count, "city_name": target_city.name}

    async def take_all_cities(self, session: AsyncSession, user: User) -> dict:
        from app.models.city import City, District
        from sqlalchemy import update as sa_update

        districts_result = await session.execute(
            sa_update(District)
            .where(District.owner_id == user.id)
            .values(owner_id=None, is_captured=False)
        )
        await session.execute(
            sa_update(City)
            .where(City.owner_id == user.id)
            .values(owner_id=None, is_fully_captured=False, captured_districts=0)
        )
        user.king_cities_count = 0
        user.fist_cities_count = 0
        await session.flush()

        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
        return {"ok": True, "removed": districts_result.rowcount}
