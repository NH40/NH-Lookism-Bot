from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.building import UserBuilding
from app.services.potion_service import potion_service


class BusinessService:

    async def _recalc_income(self, session: AsyncSession, user: User) -> None:
        result = await session.execute(
            select(
                func.sum(UserBuilding.base_income * UserBuilding.count)
            ).where(
                UserBuilding.user_id == user.id,
                UserBuilding.is_active == True,
            )
        )
        base_income = result.scalar() or 0
        total_bonus = user.income_bonus_percent + user.prestige_income_bonus
        effective_income = int(
            base_income * (1 + total_bonus / 100) * user.district_multiplier
        )
        user.income_per_minute = effective_income
        await session.flush()

    async def tick_income(self, session: AsyncSession, user: User) -> int:
        if user.income_per_minute <= 0:
            return 0

        potion_bonus = await potion_service.get_income_bonus(session, user.id)
        earned = int(user.income_per_minute * (1 + potion_bonus / 100))

        if user.referred_by and earned > 0:
            teacher_share = max(1, int(earned * user.teacher_income_share / 100))
            student_gets = earned - teacher_share
            await self._pay_teacher(session, user.referred_by, teacher_share)
        else:
            student_gets = earned

        user.nh_coins += student_gets
        await session.flush()
        return student_gets

    async def _pay_teacher(
        self, session: AsyncSession, teacher_db_id: int, amount: int
    ) -> None:
        from sqlalchemy import update
        from app.models.user import User as UserModel
        await session.execute(
            update(UserModel)
            .where(UserModel.id == teacher_db_id)
            .values(nh_coins=UserModel.nh_coins + amount)
        )

    async def buy_building(
        self, session: AsyncSession, user: User,
        building_id: str, city_id: int | None = None
    ) -> dict:
        from app.data.buildings import BUILDINGS_BY_ID
        cfg = BUILDINGS_BY_ID.get(building_id)
        if not cfg:
            return {"ok": False, "reason": "Здание не найдено"}

        if user.business_path and user.business_path != cfg.path:
            return {"ok": False, "reason": "Это здание для другого пути бизнеса"}

        if not user.business_path:
            user.business_path = cfg.path

        discount = user.building_discount_percent
        cost = max(2, int(cfg.district_cost * (1 - discount / 100)))
        # Округляем до чётного
        if cost % 2 != 0:
            cost += 1

        # Считаем свободные районы в городе
        if city_id:
            from app.models.city import District
            district_count = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city_id,
                    District.is_captured == True,
                )
            ) or 0
        else:
            from app.repositories.city_repo import city_repo
            district_count = await city_repo.get_total_districts(session, user.id)

        used_in_city = await session.scalar(
            select(func.sum(UserBuilding.district_cost)).where(
                UserBuilding.user_id == user.id,
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        ) or 0

        free = district_count - used_in_city
        if free < cost:
            return {
                "ok": False,
                "reason": f"Недостаточно районов (нужно {cost}, свободно {free})"
            }

        # Влияние по пути — только один раз
        if user.business_path == "illegal":
            # Нелегальный: -3 влияния за каждый район
            loss = cost * 3
            user.influence = max(10, user.influence - loss)
        elif user.business_path == "political":
            # Политический: +5 влияния за каждый район
            user.influence += cost * 5
        # legal: влияние не меняется

        # Ищем существующее здание в этом городе
        result = await session.execute(
            select(UserBuilding).where(
                UserBuilding.user_id == user.id,
                UserBuilding.building_type == building_id,
                UserBuilding.city_id == city_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.count += 1
            existing.district_cost += cost
        else:
            building = UserBuilding(
                user_id=user.id,
                building_type=building_id,
                path=cfg.path,
                city_id=city_id,
                count=1,
                base_income=cfg.base_income,
                district_cost=cost,
            )
            session.add(building)

        await session.flush()
        await self._recalc_income(session, user)
        return {"ok": True, "cost": cost}

    async def get_income_breakdown(
        self, session: AsyncSession, user: User
    ) -> dict:
        result = await session.execute(
            select(
                func.sum(UserBuilding.base_income * UserBuilding.count)
            ).where(
                UserBuilding.user_id == user.id,
                UserBuilding.is_active == True,
            )
        )
        base = result.scalar() or 0
        potion_bonus = await potion_service.get_income_bonus(session, user.id)
        return {
            "base_income": base,
            "final_income": user.income_per_minute,
            "total_bonus_percent": user.income_bonus_percent + user.prestige_income_bonus,
            "prestige_bonus": user.prestige_income_bonus,
            "potion_bonus": potion_bonus,
            "district_multiplier": user.district_multiplier,
        }


business_service = BusinessService()