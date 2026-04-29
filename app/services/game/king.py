import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.city import City, District
from app.services.combat_service import fight_district, fight_player
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.data.squad import ATTACK_WIN_INFLUENCE_BONUS
from app.services.game.base import GameBase, FIST_MIN_CITIES
from app.services.game.utils import notify_pvp_attack


class GameKingService(GameBase):

    async def king_attack(
        self, session: AsyncSession, user: User, city_id: int
    ) -> dict:
        if user.phase != "king":
            return {"ok": False, "reason": "Только для фазы Короля"}
        cd_key = cooldown_service.attack_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}
        city = await city_repo.get_city(session, city_id)
        if not city:
            return {"ok": False, "reason": "Город не найден"}
        dominant_id = await self._get_city_dominant_player(session, city_id, user.id)
        if dominant_id:
            defender = await user_repo.get_by_id(session, dominant_id)
            if defender and defender.phase == "king":
                return await self._king_pvp(session, user, defender, city, cd_key)
        from app.models.building import UserBuilding
        buildings_count = await session.scalar(
            select(func.count(UserBuilding.id)).where(
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        ) or 0
        from app.data.cities import KING_DISTRICT_BASE_POWER
        if buildings_count > 0:
            bot_power = int(buildings_count * 50 * city.district_power_multiplier * 0.7)
        else:
            bot_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
        bot_power = max(100, bot_power)
        result = await fight_district(session, user, bot_power)
        districts_gained = 0
        if result["win"]:
            await city_repo.init_city_districts(session, city)
            free_count = await session.scalar(
                select(func.count(District.id)).where(
                    District.city_id == city_id,
                    District.is_captured == False,
                    District.owner_id == None,
                )
            ) or 0
            if free_count > 0:
                target = min(random.randint(2, 8), free_count)
                for _ in range(target):
                    d_r = await session.execute(
                        select(District).where(
                            District.city_id == city_id,
                            District.is_captured == False,
                            District.owner_id == None,
                        ).order_by(District.number).limit(1)
                    )
                    d = d_r.scalar_one_or_none()
                    if not d:
                        break
                    d.owner_id = user.id
                    d.is_captured = True
                    city.captured_districts += 1
                    districts_gained += 1
            else:
                dominant_id = await self._get_city_dominant_player(session, city_id, user.id)
                if dominant_id:
                    target = random.randint(1, 3)
                    stolen_r = await session.execute(
                        select(District).where(
                            District.city_id == city_id,
                            District.owner_id == dominant_id,
                            District.is_captured == True,
                        ).order_by(District.number.desc()).limit(target)
                    )
                    stolen = stolen_r.scalars().all()
                    for d in stolen:
                        d.owner_id = user.id
                        districts_gained += 1
                    if stolen:
                        from app.repositories.building_repo import building_repo
                        from app.services.business_service import business_service
                        await building_repo.deactivate_buildings_on_district_loss(session, dominant_id, len(stolen))
                        dominant_user = await user_repo.get_by_id(session, dominant_id)
                        if dominant_user:
                            await business_service._recalc_income(session, dominant_user)
            real_captured = await session.scalar(
                select(func.count(District.id)).where(
                    District.city_id == city_id, District.is_captured == True,
                )
            ) or 0
            city.captured_districts = min(real_captured, city.total_districts)
            if districts_gained > 0 and not city.owner_id:
                city.owner_id = user.id
            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]
            my_in_city = await self._get_my_districts_in_city(session, user.id, city_id)
            my_cities_count = await self._count_my_king_cities(session, user.id)
            user.king_cities_count = my_cities_count
            await session.flush()
            if my_cities_count >= 10:
                return await self._promote_to_fist(session, user)
            await self._handle_attack_cd(session, user, cd_key, "king")
            await session.flush()
            return {
                "ok": True, "win": True,
                "is_crit": result["is_crit"], "user_power": result["user_power"],
                "bot_power": bot_power, "city": city.name,
                "cities_count": my_cities_count, "districts_gained": districts_gained,
                "my_in_city": my_in_city, "city_captured": city.captured_districts,
                "city_total": city.total_districts,
            }
        else:
            my_in_city = await self._get_my_districts_in_city(session, user.id, city_id)
            await self._handle_attack_cd(session, user, cd_key, "king")
            await session.flush()
            return {
                "ok": True, "win": False,
                "is_crit": result["is_crit"], "user_power": result["user_power"],
                "bot_power": bot_power, "city": city.name,
                "cities_count": user.king_cities_count, "districts_gained": 0,
                "my_in_city": my_in_city, "city_captured": city.captured_districts,
                "city_total": city.total_districts,
            }

    async def _king_pvp(
        self, session: AsyncSession,
        attacker: User, defender: User,
        city: City, cd_key: str
    ) -> dict:
        result = await fight_player(session, attacker, defender)
        if result["win"]:
            defender_districts_r = await session.execute(
                select(District).where(
                    District.city_id == city.id,
                    District.owner_id == defender.id,
                    District.is_captured == True,
                ).order_by(District.number.desc()).limit(random.randint(2, 8))
            )
            defender_districts = defender_districts_r.scalars().all()
            taken = 0
            for d in defender_districts:
                d.owner_id = attacker.id
                taken += 1
            if taken > 0:
                from app.repositories.building_repo import building_repo
                from app.services.business_service import business_service
                await building_repo.deactivate_buildings_on_district_loss(session, defender.id, taken)
                await business_service._recalc_income(session, defender)
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]
            my_cities_count = await self._count_my_king_cities(session, attacker.id)
            attacker.king_cities_count = my_cities_count
            def_cities = await self._count_my_king_cities(session, defender.id)
            defender.king_cities_count = def_cities
            if def_cities == 0:
                await self._destroy_king(session, defender)
            await notify_pvp_attack(attacker, defender, True, "king")
            await session.flush()
            if my_cities_count >= 10:
                return await self._promote_to_fist(session, attacker)
            my_in_city = await self._get_my_districts_in_city(session, attacker.id, city.id)
            await self._handle_attack_cd(session, attacker, cd_key, "king")
            await session.flush()
            return {
                "ok": True, "win": True,
                "is_crit": result["is_crit"],
                "attacker_power": result["attacker_power"],
                "defender_power": result["defender_power"],
                "defender_name": defender.full_name,
                "city": city.name, "districts_taken": taken,
                "my_in_city": my_in_city, "cities_count": my_cities_count,
            }
        else:
            await notify_pvp_attack(attacker, defender, False, "king")
            await self._handle_attack_cd(session, attacker, cd_key, "king")
            await session.flush()
            return {
                "ok": True, "win": False,
                "is_crit": result["is_crit"],
                "attacker_power": result["attacker_power"],
                "defender_power": result["defender_power"],
                "defender_name": defender.full_name,
                "city": city.name, "districts_taken": 0,
                "my_in_city": await self._get_my_districts_in_city(session, attacker.id, city.id),
                "cities_count": attacker.king_cities_count,
            }
