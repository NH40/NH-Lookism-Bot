from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.potion_service import potion_service


class BusinessService:

    async def choose_business(
        self, session: AsyncSession, user: User, building_id: str
    ) -> dict:
        """Разовый выбор здания — навсегда. Доход дальше растёт от количества
        захваченных районов, новых зданий строить нельзя (патч 1.3.1)."""
        if user.business_building_id:
            return {"ok": False, "reason": "Бизнес уже выбран"}

        from app.data.buildings import BUILDINGS_BY_ID, CANONICAL_BUILDING_IDS
        cfg = BUILDINGS_BY_ID.get(building_id)
        if not cfg or building_id not in CANONICAL_BUILDING_IDS:
            return {"ok": False, "reason": "Здание не найдено"}

        from app.repositories.city_repo import city_repo
        district_count = await city_repo.get_user_district_count(session, user.id)
        if district_count < 1:
            return {"ok": False, "reason": "Нужен хотя бы 1 захваченный район"}

        required_level = cfg.min_biz_genius * 2
        if user.business_genius_level < required_level:
            return {"ok": False, "reason": f"Требуется Гений бизнеса (Уровень) {required_level}+"}

        user.business_path = cfg.path
        user.business_building_id = building_id
        await session.flush()
        await self._recalc_income(session, user)
        return {"ok": True, "building": cfg.name, "path": cfg.path}

    @staticmethod
    async def apply_capture_influence(
        session: AsyncSession, user: User, districts_delta: int
    ) -> None:
        """Влияние за захват/потерю районов: illegal теряет, political получает."""
        if districts_delta == 0 or not user.business_building_id:
            return
        from app.config.game_balance import (
            ILLEGAL_INFLUENCE_PER_DISTRICT, POLITICAL_INFLUENCE_PER_DISTRICT,
        )
        if user.business_path == "illegal":
            from app.repositories.title_repo import title_repo
            has_great = await title_repo.has_title(session, user.id, "great_influence")
            floor = 3000 if has_great else 10
            user.influence = max(floor, user.influence + ILLEGAL_INFLUENCE_PER_DISTRICT * districts_delta)
        elif user.business_path == "political":
            delta = POLITICAL_INFLUENCE_PER_DISTRICT * districts_delta
            if delta > 0:
                # Круговые донаты дают +% к ПРИРОСТУ влияния — не усиливаем
                # потери при потере районов.
                bonus_pct = (
                    getattr(user, "influence_bonus_percent", 0)
                    + getattr(user, "clan_head_influence_bonus", 0)
                )
                delta = int(delta * (1 + bonus_pct / 100))
            user.influence = max(0, user.influence + delta)

    async def _recalc_income(self, session: AsyncSession, user: User) -> None:
        if not user.business_building_id:
            user.income_per_minute = 0
            await session.flush()
            return

        from app.data.buildings import BUILDINGS_BY_ID
        cfg = BUILDINGS_BY_ID.get(user.business_building_id)
        if not cfg:
            user.income_per_minute = 0
            await session.flush()
            return

        from app.repositories.city_repo import city_repo
        district_count = await city_repo.get_user_district_count(session, user.id)

        from app.config.game_balance import BIZ_GENIUS_CAPACITY_PCT_PER_LEVEL
        capacity_pct = user.business_genius_capacity_level * BIZ_GENIUS_CAPACITY_PCT_PER_LEVEL
        effective_districts = district_count * (1 + capacity_pct / 100)
        base_income = cfg.base_income * effective_districts

        total_bonus = self._total_bonus_percent(user, district_count)
        interim_income = int(base_income * (1 + total_bonus / 100) * user.district_multiplier)

        charles_bonus = self._charles_bonus_percent(user, district_count)
        user.income_per_minute = int(interim_income * (1 + charles_bonus / 100))

        from app.services.game_service import game_service
        await game_service._recalc_city_tax(session, user)

        await session.flush()

    @staticmethod
    def _total_bonus_percent(user: User, district_count: int) -> int:
        from app.config.game_balance import (
            BIZ_GENIUS_LEVEL_PCT_PER_LEVEL,
            BIZ_GENIUS_INCOME_PCT_PER_LEVEL,
            DIGITAL_NETWORK_BASE_PENALTY, DIGITAL_NETWORK_BONUS_PER_TIER,
            DIGITAL_NETWORK_DISTRICTS_PER_TIER, DIGITAL_NETWORK_BONUS_CAP,
            SUZERAIN_INCOME_BONUS_PCT_PER_VASSAL, SUZERAIN_INCOME_BONUS_CAP_PCT,
        )
        genius_level_bonus = user.business_genius_level * BIZ_GENIUS_LEVEL_PCT_PER_LEVEL
        genius_income_bonus = user.business_genius_income_level * BIZ_GENIUS_INCOME_PCT_PER_LEVEL
        suzerain_bonus = min(
            SUZERAIN_INCOME_BONUS_CAP_PCT,
            getattr(user, "vassal_count", 0) * SUZERAIN_INCOME_BONUS_PCT_PER_VASSAL,
        )

        network_bonus = 0
        if user.business_path == "digital":
            network_bonus = max(
                DIGITAL_NETWORK_BASE_PENALTY,
                min(
                    DIGITAL_NETWORK_BONUS_CAP,
                    DIGITAL_NETWORK_BASE_PENALTY
                    + (district_count // DIGITAL_NETWORK_DISTRICTS_PER_TIER) * DIGITAL_NETWORK_BONUS_PER_TIER,
                ),
            )

        clan_bonus = (
            getattr(user, 'clan_income_bonus', 0) + getattr(user, 'clan_donat_income_bonus', 0)
            + getattr(user, 'clan_head_income_bonus', 0) + getattr(user, 'clan_land_income_pct', 0)
        )

        # nhn_bonus/geniuses_bonus (сет Славы «Чарльз Чой») сюда НЕ входят —
        # см. _charles_bonus_percent: этот сет применяется отдельным
        # мультипликативным слоем поверх уже готового итога, а не в общую
        # сумму процентов (иначе он терял ценность, складываясь с остальным
        # вместо того чтобы усиливать финальный результат).
        return (
            user.income_bonus_percent + user.prestige_income_bonus + clan_bonus
            + genius_level_bonus + genius_income_bonus
            + network_bonus + suzerain_bonus
        )

    @staticmethod
    def _charles_bonus_percent(user: User, district_count: int) -> int:
        """Сет Славы «Чарльз Чой» — применяется ПОСЛЕДНИМ, мультипликативно
        поверх уже посчитанного итогового дохода (не в общую сумму %)."""
        nhn_bonus = min(80, (district_count // 15) * 10) if getattr(user, "fame_charles_nhn_group", False) else 0
        geniuses_bonus = 30 if getattr(user, "fame_charles_geniuses", False) else 0
        return nhn_bonus + geniuses_bonus

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

    async def get_or_create_bonus_city(self, session: AsyncSession, user: User):
        from sqlalchemy import select
        from app.models.city import City
        result = await session.execute(
            select(City).where(City.phase == "business", City.owner_id == user.id)
        )
        city = result.scalar_one_or_none()
        if not city:
            city = City(
                sector="biz",
                phase="business",
                type_id=0,
                name="Личный квартал",
                total_districts=0,
                captured_districts=0,
                is_fully_captured=True,
                owner_id=user.id,
                district_power_multiplier=1.0,
            )
            session.add(city)
            await session.flush()
        return city

    async def add_bonus_districts(self, session: AsyncSession, user: User, count: int) -> None:
        from app.models.city import City, District
        city = await self.get_or_create_bonus_city(session, user)
        for i in range(count):
            d = District(
                city_id=city.id,
                number=city.total_districts + i + 1,
                owner_id=user.id,
                is_captured=True,
            )
            session.add(d)
        city.total_districts += count
        city.captured_districts += count
        await session.flush()
        await self._recalc_income(session, user)

    async def get_income_breakdown(
        self, session: AsyncSession, user: User
    ) -> dict:
        from app.config.game_balance import (
            BIZ_GENIUS_LEVEL_PCT_PER_LEVEL, BIZ_GENIUS_CAPACITY_PCT_PER_LEVEL,
            BIZ_GENIUS_INCOME_PCT_PER_LEVEL,
        )
        from app.data.buildings import BUILDINGS_BY_ID
        from app.repositories.city_repo import city_repo

        district_count = await city_repo.get_user_district_count(session, user.id)

        has_business = bool(user.business_building_id)
        cfg = BUILDINGS_BY_ID.get(user.business_building_id) if has_business else None

        per_district_rate = cfg.base_income if cfg else 0
        base_income = per_district_rate * district_count

        total_bonus = self._total_bonus_percent(user, district_count) if has_business else 0
        potion_bonus = await potion_service.get_income_bonus(session, user.id)
        effective_income = int(base_income * (1 + total_bonus / 100) * user.district_multiplier)
        effective_final_before_charles = int(effective_income * (1 + potion_bonus / 100))

        # Сет Славы «Чарльз Чой» — последний множитель, поверх уже готового
        # итога (не в общую сумму %, см. _charles_bonus_percent).
        charles_bonus = self._charles_bonus_percent(user, district_count) if has_business else 0
        effective_final = int(effective_final_before_charles * (1 + charles_bonus / 100))

        network_bonus = 0
        if has_business and user.business_path == "digital":
            from app.config.game_balance import (
                DIGITAL_NETWORK_BASE_PENALTY, DIGITAL_NETWORK_BONUS_PER_TIER,
                DIGITAL_NETWORK_DISTRICTS_PER_TIER, DIGITAL_NETWORK_BONUS_CAP,
            )
            network_bonus = max(
                DIGITAL_NETWORK_BASE_PENALTY,
                min(
                    DIGITAL_NETWORK_BONUS_CAP,
                    DIGITAL_NETWORK_BASE_PENALTY
                    + (district_count // DIGITAL_NETWORK_DISTRICTS_PER_TIER) * DIGITAL_NETWORK_BONUS_PER_TIER,
                ),
            )

        nhn_bonus = min(80, (district_count // 15) * 10) if getattr(user, "fame_charles_nhn_group", False) else 0
        geniuses_bonus = 30 if getattr(user, "fame_charles_geniuses", False) else 0
        charles_bonus_for_circ = nhn_bonus + geniuses_bonus

        circ_passive = getattr(user, "circ_passive_income", 0) or 0
        circ_total_bonus = total_bonus + potion_bonus
        circ_per_min = max(0, int(circ_passive * (1 + circ_total_bonus / 100) * (1 + charles_bonus_for_circ / 100)))

        from app.config.game_balance import (
            SUZERAIN_INCOME_BONUS_PCT_PER_VASSAL, SUZERAIN_INCOME_BONUS_CAP_PCT,
        )
        suzerain_bonus = min(
            SUZERAIN_INCOME_BONUS_CAP_PCT,
            getattr(user, "vassal_count", 0) * SUZERAIN_INCOME_BONUS_PCT_PER_VASSAL,
        )

        from app.config.game_balance import VASSAL_TRIBUTE_PERCENT
        from sqlalchemy import select, func
        from app.models.user import User as _User
        vassal_income_sum = await session.scalar(
            select(func.coalesce(func.sum(_User.income_per_minute), 0)).where(_User.suzerain_id == user.id)
        ) or 0
        vassal_tribute_income = int(vassal_income_sum * VASSAL_TRIBUTE_PERCENT / 100)

        return {
            "has_business": has_business,
            "building_name": cfg.name if cfg else None,
            "building_emoji": cfg.emoji if cfg else None,
            "building_path": cfg.path if cfg else None,
            "district_count": district_count,
            "per_district_rate": per_district_rate,
            "base_income": base_income,
            "final_income": effective_final,
            "total_bonus_percent": total_bonus,
            "genius_level": user.business_genius_level,
            "genius_capacity_level": user.business_genius_capacity_level,
            "genius_discount_level": user.business_genius_discount_level,
            "genius_income_level": user.business_genius_income_level,
            "genius_level_bonus": user.business_genius_level * BIZ_GENIUS_LEVEL_PCT_PER_LEVEL,
            "genius_capacity_bonus": user.business_genius_capacity_level * BIZ_GENIUS_CAPACITY_PCT_PER_LEVEL,
            "genius_income_bonus": user.business_genius_income_level * BIZ_GENIUS_INCOME_PCT_PER_LEVEL,
            "network_bonus": network_bonus,
            "prestige_bonus": user.prestige_income_bonus,
            "potion_bonus": potion_bonus,
            "clan_income_bonus": getattr(user, 'clan_income_bonus', 0),
            "clan_donat_income_bonus": getattr(user, 'clan_donat_income_bonus', 0),
            "clan_head_income_bonus": getattr(user, 'clan_head_income_bonus', 0),
            "clan_land_income_bonus": getattr(user, 'clan_land_income_pct', 0),
            "suzerain_bonus": suzerain_bonus,
            "nhn_bonus": nhn_bonus,
            "geniuses_bonus": geniuses_bonus,
            "charles_bonus_pct": charles_bonus,
            "district_multiplier": user.district_multiplier,
            "skills_bonus": user.income_bonus_percent,
            "circ_passive_income": circ_passive,
            "circ_passive_per_min": circ_per_min,
            "vassal_tribute_income": vassal_tribute_income,
        }


business_service = BusinessService()
