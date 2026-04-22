from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.building import UserBuilding
from app.data.buildings import BUILDINGS_BY_ID


class BuildingRepo:

    async def get_user_buildings(
        self, session: AsyncSession, user_id: int
    ) -> list[UserBuilding]:
        result = await session.execute(
            select(UserBuilding).where(
                UserBuilding.user_id == user_id,
                UserBuilding.is_active == True,
            )
        )
        return result.scalars().all()

    async def get_used_districts(
        self, session: AsyncSession, user_id: int
    ) -> int:
        """Сколько районов потрачено на здания."""
        result = await session.scalar(
            select(func.sum(UserBuilding.district_cost)).where(
                UserBuilding.user_id == user_id,
                UserBuilding.is_active == True,
            )
        )
        return result or 0

    async def calc_base_income(
        self, session: AsyncSession, user_id: int
    ) -> int:
        result = await session.scalar(
            select(
                func.sum(UserBuilding.base_income * UserBuilding.count)
            ).where(
                UserBuilding.user_id == user_id,
                UserBuilding.is_active == True,
            )
        )
        return result or 0

    async def deactivate_buildings_on_district_loss(
        self, session: AsyncSession, user_id: int, districts_lost: int
    ) -> int:
        """При потере районов деактивирует здания (самые новые первыми)."""
        buildings = await session.execute(
            select(UserBuilding).where(
                UserBuilding.user_id == user_id,
                UserBuilding.is_active == True,
            ).order_by(UserBuilding.created_at.desc())
        )
        buildings = buildings.scalars().all()

        freed = 0
        deactivated = 0
        for b in buildings:
            if freed >= districts_lost:
                break
            b.is_active = False
            freed += b.district_cost
            deactivated += 1

        await session.flush()
        return deactivated

    async def get_buildings_display(
        self, session: AsyncSession, user_id: int
    ) -> str:
        buildings = await self.get_user_buildings(session, user_id)
        if not buildings:
            return "Зданий нет"
        lines = []
        for b in buildings:
            cfg = BUILDINGS_BY_ID.get(b.building_type)
            name = cfg.name if cfg else b.building_type
            emoji = cfg.emoji if cfg else "🏢"
            income = b.base_income * b.count
            lines.append(
                f"{emoji} {name} ×{b.count} — {income}/мин"
            )
        return "\n".join(lines)


building_repo = BuildingRepo()