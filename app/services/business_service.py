from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.building import UserBuilding
from app.services.potion_service import potion_service


class BusinessService:

    @staticmethod
    def _biz_genius_bonus(user: User) -> int:
        from app.constants.raid import BIZ_GENIUS_INCOME_BONUS
        lvl = getattr(user, "business_genius_level", 0)
        if lvl <= 0:
            return 0
        return BIZ_GENIUS_INCOME_BONUS[min(lvl, len(BIZ_GENIUS_INCOME_BONUS)) - 1]

    @staticmethod
    async def _digital_network_bonus(session: AsyncSession, user: User) -> int:
        """Сетевой эффект: +10% за каждые 10 цифровых зданий, макс +50%."""
        if getattr(user, "business_path", None) != "digital":
            return 0
        count = await session.scalar(
            select(func.sum(UserBuilding.count)).where(
                UserBuilding.user_id == user.id,
                UserBuilding.is_active == True,
                UserBuilding.path == "digital",
            )
        ) or 0
        return min(50, (count // 10) * 10)

    async def _recalc_income(self, session: AsyncSession, user: User) -> None:
        result = await session.execute(
            select(
                func.sum(UserBuilding.base_income * UserBuilding.count)
            ).where(
                UserBuilding.user_id == user.id,
                UserBuilding.is_active == True,
                UserBuilding.count > 0,
            )
        )
        base_income = result.scalar() or 0
        clan_bonus = getattr(user, 'clan_income_bonus', 0) + getattr(user, 'clan_donat_income_bonus', 0)
        biz_genius_bonus = self._biz_genius_bonus(user)
        network_bonus = await self._digital_network_bonus(session, user)
        total_bonus = user.income_bonus_percent + user.prestige_income_bonus + clan_bonus + biz_genius_bonus + network_bonus
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
            await self._pay_teacher(session, user.referred_by, user.id, teacher_share)
        else:
            student_gets = earned

        user.nh_coins += student_gets
        await session.flush()
        return student_gets

    async def _pay_teacher(
        self, session: AsyncSession, teacher_db_id: int, student_db_id: int, amount: int
    ) -> None:
        from sqlalchemy import update
        from app.models.user import User as UserModel
        from app.models.referral import Referral

        # Use ORM get so the cached identity-map object is updated in-place,
        # preventing a later flush of the same teacher row from overwriting this payment.
        teacher = await session.get(UserModel, teacher_db_id)
        if teacher:
            teacher.nh_coins += amount

        await session.execute(
            update(Referral)
            .where(
                Referral.teacher_id == teacher_db_id,
                Referral.student_id == student_db_id,
            )
            .values(total_earned=Referral.total_earned + amount)
        )

    @staticmethod
    def _apply_demolish_influence(user: User, districts: int) -> None:
        """Корректирует влияние при сносе зданий.
        Политика: теряет влияние обратно (cost * 5).
        Нелегальный: возвращает влияние (cost * 5).
        """
        if districts <= 0:
            return
        delta = districts * 5
        if user.business_path == "political":
            user.influence = max(0, user.influence - delta)
        elif user.business_path == "illegal":
            user.influence += delta

    @staticmethod
    def _genius_discount(user: User) -> int:
        from app.constants.raid import BIZ_GENIUS_DISCOUNT
        lvl = getattr(user, "business_genius_level", 0)
        if lvl <= 0:
            return 0
        return BIZ_GENIUS_DISCOUNT[min(lvl, len(BIZ_GENIUS_DISCOUNT)) - 1]

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

        discount = user.building_discount_percent + self._genius_discount(user)
        cost = max(2, int(cfg.district_cost * (1 - discount / 100)))
        if cost % 2 != 0:
            cost += 1

        # Считаем районы в городе
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
            district_count += getattr(user, "bonus_business_districts", 0)

        # Занятые районы — только активные здания с count > 0
        used_in_city = await session.scalar(
            select(func.sum(UserBuilding.district_cost)).where(
                UserBuilding.user_id == user.id,
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
                UserBuilding.count > 0,
            )
        ) or 0

        free = district_count - used_in_city
        if free < cost:
            return {
                "ok": False,
                "reason": f"Недостаточно районов (нужно {cost}, свободно {free})"
            }

        # Для fist-городов: лимит бизнесов по размеру города
        if city_id:
            from app.models.city import City as CityModel
            from app.data.cities import FIST_CITY_MAX_BUSINESSES
            city_obj = await session.get(CityModel, city_id)
            if city_obj and city_obj.phase == "fist":
                max_biz = FIST_CITY_MAX_BUSINESSES.get(city_obj.total_districts, 1)
                existing_biz = await session.scalar(
                    select(func.count(UserBuilding.id)).where(
                        UserBuilding.user_id == user.id,
                        UserBuilding.city_id == city_id,
                        UserBuilding.is_active == True,
                    )
                ) or 0
                if existing_biz >= max_biz:
                    sfx = "бизнес" if max_biz == 1 else "бизнеса"
                    return {"ok": False, "reason": f"В этом городе максимум {max_biz} {sfx}"}

        if user.business_path == "illegal":
            loss = cost * 5
            from app.repositories.title_repo import title_repo
            has_great = await title_repo.has_title(session, user.id, "great_influence")
            min_influence = 3000 if has_great else 10
            user.influence = max(min_influence, user.influence - loss)
        elif user.business_path == "political":
            user.influence += cost * 5
        result = await session.execute(
            select(UserBuilding).where(
                UserBuilding.user_id == user.id,
                UserBuilding.building_type == building_id,
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
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

    async def buy_building_max(
        self, session: AsyncSession, user: User, building_id: str
    ) -> dict:
        from app.data.buildings import BUILDINGS_BY_ID
        from app.models.city import District, City as CityModel

        cfg = BUILDINGS_BY_ID.get(building_id)
        if not cfg:
            return {"ok": False, "reason": "Здание не найдено", "count": 0}

        discount = user.building_discount_percent + self._genius_discount(user)
        cost = max(2, int(cfg.district_cost * (1 - discount / 100)))
        if cost % 2 != 0:
            cost += 1

        has_great = False
        if user.business_path == "illegal":
            from app.repositories.title_repo import title_repo
            has_great = await title_repo.has_title(session, user.id, "great_influence")
        min_influence = 3000 if has_great else 10

        result = await session.execute(
            select(District.city_id, func.count(District.id).label("cnt"))
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                District.city_id.isnot(None),
            )
            .group_by(District.city_id)
        )
        city_rows = result.all()

        total_built = 0
        for city_id, district_count in city_rows:
            city_obj = await session.get(CityModel, city_id)
            if city_obj and city_obj.phase == "fist":
                from app.data.cities import FIST_CITY_MAX_BUSINESSES
                max_biz = FIST_CITY_MAX_BUSINESSES.get(city_obj.total_districts, 1)
                existing_biz = await session.scalar(
                    select(func.count(UserBuilding.id)).where(
                        UserBuilding.user_id == user.id,
                        UserBuilding.city_id == city_id,
                        UserBuilding.is_active == True,
                    )
                ) or 0
                if existing_biz >= max_biz:
                    continue

            used_in_city = await session.scalar(
                select(func.sum(UserBuilding.district_cost)).where(
                    UserBuilding.user_id == user.id,
                    UserBuilding.city_id == city_id,
                    UserBuilding.is_active == True,
                    UserBuilding.count > 0,
                )
            ) or 0
            free = district_count - used_in_city
            n = free // cost
            if n <= 0:
                continue

            if user.business_path == "illegal":
                user.influence = max(min_influence, user.influence - cost * n * 5)
            elif user.business_path == "political":
                user.influence += cost * n * 5

            res2 = await session.execute(
                select(UserBuilding).where(
                    UserBuilding.user_id == user.id,
                    UserBuilding.building_type == building_id,
                    UserBuilding.city_id == city_id,
                    UserBuilding.is_active == True,
                )
            )
            existing = res2.scalar_one_or_none()
            if existing:
                existing.count += n
                existing.district_cost += cost * n
            else:
                session.add(UserBuilding(
                    user_id=user.id,
                    building_type=building_id,
                    path=cfg.path,
                    city_id=city_id,
                    count=n,
                    base_income=cfg.base_income,
                    district_cost=cost * n,
                ))
            total_built += n

        if total_built > 0:
            await session.flush()
            await self._recalc_income(session, user)
        return {"ok": True, "count": total_built, "cost_each": cost}

    async def demolish_all_city(
        self, session: AsyncSession, user: User, city_id: int
    ) -> dict:
        result = await session.execute(
            select(UserBuilding).where(
                UserBuilding.user_id == user.id,
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        )
        buildings = result.scalars().all()
        total_count = sum(b.count for b in buildings)
        total_districts = sum(b.district_cost for b in buildings)
        for b in buildings:
            await session.delete(b)
        await session.flush()
        if buildings:
            self._apply_demolish_influence(user, total_districts)
            await self._recalc_income(session, user)
        return {"ok": True, "count": total_count}

    async def demolish_all(
        self, session: AsyncSession, user: User
    ) -> dict:
        result = await session.execute(
            select(UserBuilding).where(
                UserBuilding.user_id == user.id,
                UserBuilding.is_active == True,
            )
        )
        buildings = result.scalars().all()
        total_count = sum(b.count for b in buildings)
        total_districts = sum(b.district_cost for b in buildings)
        for b in buildings:
            await session.delete(b)
        await session.flush()
        if buildings:
            self._apply_demolish_influence(user, total_districts)
            await self._recalc_income(session, user)
        return {"ok": True, "count": total_count}

    async def get_income_breakdown(
        self, session: AsyncSession, user: User
    ) -> dict:
        result = await session.execute(
            select(
                func.sum(UserBuilding.base_income * UserBuilding.count)
            ).where(
                UserBuilding.user_id == user.id,
                UserBuilding.is_active == True,
                UserBuilding.count > 0,
            )
        )
        base = result.scalar() or 0
        potion_bonus = await potion_service.get_income_bonus(session, user.id)
        clan_upgrade_bonus = getattr(user, 'clan_income_bonus', 0)
        clan_donat_bonus = getattr(user, 'clan_donat_income_bonus', 0)
        clan_bonus = clan_upgrade_bonus + clan_donat_bonus
        biz_genius_bonus = self._biz_genius_bonus(user)
        network_bonus = await self._digital_network_bonus(session, user)
        other_bonus = user.income_bonus_percent + user.prestige_income_bonus
        total_bonus = other_bonus + clan_bonus + biz_genius_bonus + network_bonus

        effective_income = int(base * (1 + total_bonus / 100) * user.district_multiplier)
        effective_final = int(effective_income * (1 + potion_bonus / 100))

        # Пассивный доход от круговых донатов: NHCoin/мин (уже за минуту)
        # Применяем те же % баффы что и в income_tick: навыки + пробуждение + клан + зелье
        circ_passive = getattr(user, "circ_passive_income", 0) or 0
        circ_total_bonus = total_bonus + potion_bonus
        circ_per_min = max(0, int(circ_passive * (1 + circ_total_bonus / 100)))

        return {
            "base_income": base,
            "final_income": effective_final,
            "total_bonus_percent": total_bonus,
            "prestige_bonus": user.prestige_income_bonus,
            "potion_bonus": potion_bonus,
            "clan_income_bonus": clan_upgrade_bonus,
            "clan_donat_income_bonus": clan_donat_bonus,
            "district_multiplier": user.district_multiplier,
            "skills_bonus": user.income_bonus_percent,
            "biz_genius_bonus": biz_genius_bonus,
            "network_bonus": network_bonus,
            "circ_passive_income": circ_passive,
            "circ_passive_per_min": circ_per_min,
        }


business_service = BusinessService()