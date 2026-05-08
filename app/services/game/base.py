import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.city import District
from app.services.cooldown_service import cooldown_service

ATTACK_CD: dict[str, int] = {
    "gang":    60,
    "king":    300,
    "fist":    600,
    "emperor": 1000,
}

FIST_MIN_CITIES = 10

FIST_BOT_CONFIGS = [
    {"name": "Рю",  "ratio": 0.80},
    {"name": "Со",  "ratio": 0.90},
    {"name": "Чан", "ratio": 1.00},
    {"name": "Пэк", "ratio": 1.10},
    {"name": "Ли",  "ratio": 1.20},
]


class GameBase:

    def _get_district_power(self, district_number: int, multiplier: float) -> int:
        return max(10, int(10 * (district_number ** 0.6) * multiplier))

    async def _get_my_districts_in_city(
        self, session: AsyncSession, user_id: int, city_id: int
    ) -> int:
        r = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user_id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        )
        return r or 0

    async def _count_my_king_cities(
        self, session: AsyncSession, user_id: int
    ) -> int:
        r = await session.execute(
            select(District.city_id).where(
                District.owner_id == user_id,
                District.is_captured == True,
            ).distinct()
        )
        return len(r.scalars().all())

    async def _get_city_dominant_player(
        self, session: AsyncSession, city_id: int, exclude_user_id: int
    ) -> int | None:
        from sqlalchemy import desc
        r = await session.execute(
            select(District.owner_id, func.count(District.id).label("cnt"))
            .where(
                District.city_id == city_id,
                District.is_captured == True,
                District.owner_id != None,
                District.owner_id != exclude_user_id,
            )
            .group_by(District.owner_id)
            .order_by(desc("cnt"))
            .limit(1)
        )
        row = r.first()
        return row[0] if row else None

    async def _get_max_extra_attacks_async(
        self, session: AsyncSession, user: User
    ) -> int:
        if not user.double_attack:
            return 0
        from app.models.skill import UserPathSkills
        path_skill_r = await session.execute(
            select(UserPathSkills).where(
                UserPathSkills.user_id == user.id,
                UserPathSkills.skill_id == "mon_dattack",
            )
        )
        has_path_attack = path_skill_r.scalar_one_or_none() is not None
        from app.repositories.title_repo import title_repo
        has_monster_set = await title_repo.has_set(session, user.id, "monster")
        count = 0
        if has_path_attack:
            count += 1
        if has_monster_set:
            count += 1
        return count

    async def _handle_attack_cd(
        self, session: AsyncSession, user: User, cd_key: str, phase: str
    ) -> None:
        if user.extra_attack_count > 0:
            user.extra_attack_count -= 1
            return
        base_cd = ATTACK_CD[phase]
        from app.models.skill import UserMastery
        mr = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = mr.scalar_one_or_none()
        speed_pct = 0
        if mastery:
            speed_pct = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(mastery.speed, 0)
        from app.repositories.title_repo import title_repo
        has_flow = await title_repo.has_set(session, user.id, "flow")
        if has_flow:
            speed_pct = min(80, speed_pct + 15)
        cd = max(10, int(base_cd * (1 - speed_pct / 100)))
        await cooldown_service.set_cooldown(cd_key, cd)
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)

    async def _demote_fist_to_king(
        self, session: AsyncSession, user: User
    ) -> None:
        user.phase = "king"
        user.fist_cities_count = 0
        user.king_cities_count = await self._count_my_king_cities(session, user.id)
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
        # Пересоздаём ботов-королей по текущей мощи игрока
        from sqlalchemy import delete as sql_delete
        from app.models.king_bot import KingBot
        await session.execute(sql_delete(KingBot).where(KingBot.user_id == user.id))
        await session.flush()
        try:
            from app.bot_instance import get_bot
            bot = get_bot()
            if bot and user.notifications_enabled:
                await bot.send_message(
                    user.tg_id,
                    "⚠️ <b>Вы потеряли слишком много городов!</b>\n\n"
                    "Вы понижены до фазы Короля.\n"
                    "Захватите 10 городов снова чтобы вернуть статус Кулака.",
                    parse_mode="HTML",
                )
        except Exception:
            pass

    async def _promote_to_king(
        self, session: AsyncSession, user: User, city
    ) -> dict:
        user.phase = "king"
        user.king_cities_count = 1
        city.owner_id = user.id
        city.is_fully_captured = True
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
        # Удаляем старых ботов-королей, чтобы пересоздать по текущей мощи игрока
        from sqlalchemy import delete as sql_delete
        from app.models.king_bot import KingBot
        await session.execute(sql_delete(KingBot).where(KingBot.user_id == user.id))
        await session.flush()
        return {
            "ok": True, "promoted": True, "new_phase": "king",
            "message": (
                f"🎉 Вы захватили <b>{city.name}</b> и стали Королём!\n\n"
                f"Захватите районы в 10 городах чтобы стать Кулаком."
            )
        }

    async def _promote_to_fist(self, session: AsyncSession, user: User) -> dict:
        user.phase = "fist"
        user.fist_cities_count = FIST_MIN_CITIES
        user.extra_attack_count = await self._get_max_extra_attacks_async(session, user)
        # Удаляем старых ботов — при следующем вызове get_fist_bots создадутся
        # новые с актуальной боевой мощью игрока
        from sqlalchemy import delete as sql_delete
        from app.models.city import FistBot
        await session.execute(sql_delete(FistBot).where(FistBot.challenger_id == user.id))
        await session.flush()
        return {
            "ok": True, "promoted": True, "new_phase": "fist",
            "message": (
                "✊ Вы набрали районы в 10 городах и стали Кулаком!\n\n"
                "Победите 10 кулаков чтобы стать Императором."
            )
        }

    async def _promote_to_emperor(self, session: AsyncSession, user: User) -> dict:
        user.phase = "emperor"
        user.extra_attack_count = 0
        await session.flush()
        return {
            "ok": True, "promoted": True, "new_phase": "emperor",
            "message": "👑 Вы победили 10 кулаков и стали Императором!"
        }

    async def _destroy_gang(self, session: AsyncSession, user: User) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user, keep_ui=True, keep_progress=True)
        return {"ok": True, "destroyed": True, "message": "💀 Ваша банда уничтожена! Начинайте сначала."}

    async def _destroy_king(self, session: AsyncSession, user: User) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user, keep_ui=True, keep_progress=True)
        return {"ok": True, "destroyed": True, "message": "💀 Вы потеряли все города!"}
    
    async def _give_fist_cities(
        self, session: AsyncSession, user: User, count: int
    ) -> None:
        """Выдаёт реальные районы в fist городах при победе кулака."""
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo
        from sqlalchemy import select, func

        sector = user.sector or "Н"

        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == "fist",
            ).order_by(City.id)
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

            # Выдаём случайное количество районов (2–6)
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

    async def _take_fist_cities_from(
        self, session: AsyncSession, user: User, count: int
    ) -> int:
        """Забирает fist-районы у игрока (при проигрыше или потере в PvP).

        Освобождает до `count` городов с их районами, уничтожает здания
        пропорционально потерянным районам. Возвращает реальное число
        забранных городов.
        """
        from app.models.city import City, District
        from sqlalchemy import select, func, desc
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