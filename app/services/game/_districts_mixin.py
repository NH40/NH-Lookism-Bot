"""DistrictsMixin — выдача / изъятие районов (fist-города и king-города)."""
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.user import User


class DistrictsMixin:

    async def _give_fist_city_one(
        self, session: AsyncSession, user: User, total_districts: int
    ) -> None:
        """Выдаёт игроку один fist-город с total_districts районами (все районы его)."""
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo

        sector = user.sector or "Н"
        type_id = {8: 2, 16: 3, 32: 4, 64: 5}.get(total_districts, 2)

        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == "fist",
                City.total_districts == total_districts,
            ).order_by(City.id)
        )
        all_cities = result.scalars().all()

        target_city = None
        for city in all_cities:
            my_in_city = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_in_city == 0:
                target_city = city
                break

        if not target_city:
            target_city = await self._create_fist_city(
                session, sector, type_id, total_districts, all_cities
            )

        await city_repo.init_city_districts(session, target_city)
        await session.flush()

        districts_r = await session.execute(
            select(District).where(
                District.city_id == target_city.id,
                District.owner_id == None,
                District.is_captured == False,
            ).order_by(District.number)
        )
        districts = districts_r.scalars().all()

        if not districts:
            target_city = await self._create_fist_city(
                session, sector, type_id, total_districts, all_cities, extra=True
            )
            await city_repo.init_city_districts(session, target_city)
            await session.flush()
            districts_r = await session.execute(
                select(District).where(District.city_id == target_city.id).order_by(District.number)
            )
            districts = districts_r.scalars().all()

        for d in districts:
            d.owner_id = user.id
            d.is_captured = True

        target_city.captured_districts = len(districts)
        target_city.owner_id = user.id
        target_city.is_fully_captured = True
        await session.flush()

    async def _create_fist_city(
        self, session: AsyncSession, sector: str, type_id: int,
        total_districts: int, existing_cities: list, extra: bool = False
    ):
        """Создаёт новый fist-город в секторе."""
        from app.models.city import City
        from app.data.cities import CITY_NAMES_BY_SECTOR
        names = CITY_NAMES_BY_SECTOR.get(sector, [])
        used_names = {c.name for c in existing_cities}
        available = [n for n in names if n not in used_names]
        suffix = "-new" if extra else f"-{len(existing_cities)+1}"
        name = random.choice(available) if available else f"Кулак-{sector}-{total_districts}{suffix}"
        city = City(
            sector=sector, phase="fist", type_id=type_id, name=name,
            total_districts=total_districts, captured_districts=0,
            is_fully_captured=False, district_power_multiplier=1.0,
        )
        session.add(city)
        await session.flush()
        return city

    async def _give_fist_cities(
        self, session: AsyncSession, user: User, count: int
    ) -> None:
        """Выдаёт реальные районы в fist городах при победе кулака."""
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo

        sector = user.sector or "Н"
        result = await session.execute(
            select(City).where(City.sector == sector, City.phase == "fist").order_by(City.id)
        )
        all_cities = result.scalars().all()

        given = 0
        for city in all_cities:
            if given >= count:
                break
            my_in_city = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_in_city > 0:
                continue

            await city_repo.init_city_districts(session, city)
            await session.flush()

            districts_r = await session.execute(
                select(District).where(
                    District.city_id == city.id,
                    District.is_captured == False,
                    District.owner_id == None,
                ).order_by(District.number).limit(random.randint(2, 6))
            )
            districts = districts_r.scalars().all()
            for d in districts:
                d.owner_id = user.id
                d.is_captured = True
                city.captured_districts += 1

            if not city.owner_id:
                city.owner_id = user.id
            given += 1

        await session.flush()

    async def _take_king_cities_from(
        self, session: AsyncSession, user: User, count: int
    ) -> int:
        """Забирает king-районы у игрока при падении с фазы Кулака."""
        from app.models.city import City, District
        from app.repositories.building_repo import building_repo
        from app.services.business_service import business_service

        cities_r = await session.execute(
            select(District.city_id, func.count(District.id).label("cnt"))
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                City.phase != "fist",
            )
            .group_by(District.city_id)
            .order_by(desc("cnt"))
        )
        city_groups = cities_r.all()

        taken_cities = 0
        total_districts_lost = 0

        for row in city_groups:
            if taken_cities >= count:
                break
            city_id = row[0]

            districts_r = await session.execute(
                select(District).where(
                    District.owner_id == user.id,
                    District.city_id == city_id,
                    District.is_captured == True,
                )
            )
            districts = districts_r.scalars().all()
            for d in districts:
                d.owner_id = None
                d.is_captured = False
                total_districts_lost += 1

            city_r = await session.execute(select(City).where(City.id == city_id))
            city_obj = city_r.scalar_one_or_none()
            if city_obj:
                city_obj.captured_districts = max(0, city_obj.captured_districts - len(districts))
                if city_obj.owner_id == user.id:
                    city_obj.owner_id = None
                city_obj.is_fully_captured = False

            taken_cities += 1

        if total_districts_lost > 0:
            await building_repo.deactivate_buildings_on_district_loss(
                session, user.id, total_districts_lost
            )
            await business_service._recalc_income(session, user)

        await session.flush()
        return taken_cities

    async def _take_fist_cities_from(
        self, session: AsyncSession, user: User, count: int
    ) -> int:
        """Забирает fist-районы у игрока (при проигрыше или потере в PvP)."""
        from app.models.city import City, District
        from app.repositories.building_repo import building_repo
        from app.services.business_service import business_service

        cities_r = await session.execute(
            select(District.city_id, func.count(District.id).label("cnt"))
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                City.phase == "fist",
            )
            .group_by(District.city_id)
            .order_by(desc("cnt"))
        )
        city_groups = cities_r.all()

        taken_cities = 0
        total_districts_lost = 0

        for row in city_groups:
            if taken_cities >= count:
                break
            city_id = row[0]

            districts_r = await session.execute(
                select(District).where(
                    District.owner_id == user.id,
                    District.city_id == city_id,
                    District.is_captured == True,
                )
            )
            districts = districts_r.scalars().all()
            for d in districts:
                d.owner_id = None
                d.is_captured = False
                total_districts_lost += 1

            city_r = await session.execute(select(City).where(City.id == city_id))
            city = city_r.scalar_one_or_none()
            if city:
                city.captured_districts = max(0, city.captured_districts - len(districts))
                if city.owner_id == user.id:
                    city.owner_id = None
                city.is_fully_captured = False

            taken_cities += 1

        if total_districts_lost > 0:
            await building_repo.deactivate_buildings_on_district_loss(
                session, user.id, total_districts_lost
            )
            await business_service._recalc_income(session, user)

        await session.flush()
        return taken_cities
