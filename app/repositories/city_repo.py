import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.city import City, District
from app.models.user import User


class CityRepo:

    async def get_city(
        self, session: AsyncSession, city_id: int
    ) -> City | None:
        result = await session.execute(
            select(City).where(City.id == city_id)
        )
        return result.scalar_one_or_none()

    async def get_cities_by_sector(
        self, session: AsyncSession, sector: str, phase: str
    ) -> list[City]:
        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == phase,
            )
        )
        return result.scalars().all()

    async def get_next_district(
        self, session: AsyncSession, city_id: int
    ) -> District | None:
        """Первый незахваченный район города."""
        result = await session.execute(
            select(District).where(
                District.city_id == city_id,
                District.is_captured == False,
            ).order_by(District.number).limit(1)
        )
        return result.scalar_one_or_none()

    async def capture_district(
        self,
        session: AsyncSession,
        district: District,
        user_id: int,
        city: City,
    ) -> None:
        district.owner_id = user_id
        district.is_captured = True
        city.captured_districts += 1

        # Увеличиваем множитель силы района
        city.district_power_multiplier += random.uniform(0.05, 0.10)

        if city.captured_districts >= city.total_districts:
            city.is_fully_captured = True
            city.owner_id = user_id

        await session.flush()

    async def lose_district(
        self,
        session: AsyncSession,
        user_id: int,
        city_id: int,
    ) -> District | None:
        """Забирает последний захваченный район у пользователя в городе."""
        result = await session.execute(
            select(District).where(
                District.city_id == city_id,
                District.owner_id == user_id,
                District.is_captured == True,
            ).order_by(District.number.desc())
        )
        district = result.scalar_one_or_none()
        if district:
            district.owner_id = None
            district.is_captured = False
            city = await self.get_city(session, city_id)
            if city:
                city.captured_districts = max(0, city.captured_districts - 1)
                city.is_fully_captured = False
                if city.owner_id == user_id:
                    city.owner_id = None
            await session.flush()
        return district

    async def get_user_district_count(
        self, session: AsyncSession, user_id: int
    ) -> int:
        result = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user_id,
                District.is_captured == True,
            )
        )
        return result or 0

    async def get_total_districts(
        self, session: AsyncSession, user_id: int
    ) -> int:
        """Все захваченные районы пользователя (для бизнеса)."""
        return await self.get_user_district_count(session, user_id)

    async def get_district_power(
        self, city: City, district_number: int
    ) -> int:
        from app.data.cities import DISTRICT_BASE_POWER
        power = int(
            DISTRICT_BASE_POWER
            * (district_number ** 0.4)
            * city.district_power_multiplier
        )
        return max(10, power)

    async def init_city_districts(
        self, session: AsyncSession, city: City
    ) -> None:
        """Создаёт районы для города если их нет."""
        existing = await session.scalar(
            select(func.count(District.id)).where(
                District.city_id == city.id
            )
        )
        if existing:
            return
        for i in range(1, city.total_districts + 1):
            d = District(city_id=city.id, number=i)
            session.add(d)
        await session.flush()

    async def get_king_cities_count(
        self, session: AsyncSession, user_id: int
    ) -> int:
        result = await session.scalar(
            select(func.count(City.id)).where(
                City.owner_id == user_id,
                City.is_fully_captured == True,
            )
        )
        return result or 0

    async def get_available_gang_cities(
        self, session: AsyncSession, sector: str
    ) -> list[City]:
        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == "gang",
                City.is_fully_captured == False,
            ).order_by(City.type_id)
        )
        return result.scalars().all()

    async def get_available_king_cities(
        self, session: AsyncSession, sector: str
    ) -> list[City]:
        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == "king",
            ).order_by(City.type_id)
        )
        return result.scalars().all()


city_repo = CityRepo()