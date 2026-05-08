import random
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.city import District
from app.services.combat_service import fight_district, fight_player
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.data.squad import ATTACK_WIN_INFLUENCE_BONUS
from app.services.game.base import GameBase
from app.services.game.utils import notify_pvp_attack
from app.utils.truce import is_truce_active


class GameGangService(GameBase):

    async def choose_sector(
        self, session: AsyncSession, user: User, sector: str
    ) -> dict:
        if user.sector:
            return {"ok": False, "reason": "Сектор уже выбран"}
        from app.data.cities import SECTORS
        if sector not in SECTORS:
            return {"ok": False, "reason": "Неверный сектор"}
        user.sector = sector
        await session.flush()
        return {"ok": True, "sector": sector}

    async def choose_gang_city(self, session, user, city_id):
        if user.gang_city_id:
            return {"ok": False, "reason": "Город уже выбран"}
        city = await city_repo.get_city(session, city_id)
        if not city:
            return {"ok": False, "reason": "Город не найден"}
        await city_repo.init_city_districts(session, city)
        user.gang_city_id = city_id
        await session.flush()  # ← обязательно
        return {"ok": True, "city": city.name}

    async def gang_get_situation(
        self, session: AsyncSession, user: User
    ) -> dict:
        if not user.gang_city_id:
            return {"ok": False, "reason": "Город не выбран"}
        city = await city_repo.get_city(session, user.gang_city_id)
        if not city:
            return {"ok": False, "reason": "Город не найден"}
        await city_repo.init_city_districts(session, city)
        my_districts = await self._get_my_districts_in_city(session, user.id, user.gang_city_id)
        next_bot_r = await session.execute(
            select(District).where(
                District.city_id == user.gang_city_id,
                District.is_captured == False,
            ).order_by(District.number).limit(1)
        )
        next_bot = next_bot_r.scalar_one_or_none()
        bot_district_power = None
        if next_bot:
            bot_district_power = self._get_district_power(next_bot.number, city.district_power_multiplier)
        rivals = await user_repo.get_players_in_city(session, user.gang_city_id, user.id)
        rival_info = []
        for rival in rivals:
            rival_districts = await self._get_my_districts_in_city(session, rival.id, user.gang_city_id)
            if rival_districts > 0:
                rival_info.append({
                    "id": rival.id, "name": rival.full_name,
                    "combat_power": rival.combat_power, "districts": rival_districts,
                })
        return {
            "ok": True, "city": city,
            "my_districts": my_districts,
            "total_districts": city.total_districts,
            "next_bot_district": next_bot,
            "bot_district_power": bot_district_power,
            "rivals": rival_info,
            "city_fully_captured": city.is_fully_captured,
        }

    async def gang_attack_bot(self, session: AsyncSession, user: User) -> dict:
        if user.phase != "gang":
            return {"ok": False, "reason": "Только для фазы Банды"}
        if not user.gang_city_id:
            return {"ok": False, "reason": "Выберите город"}
        if is_truce_active(user):
            return {"ok": False, "reason": "Во время перемирия нельзя атаковать"}
        cd_key = cooldown_service.attack_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}
        city = await city_repo.get_city(session, user.gang_city_id)
        if not city:
            return {"ok": False, "reason": "Город не найден"}
        await city_repo.init_city_districts(session, city)
        next_r = await session.execute(
            select(District).where(
                District.city_id == user.gang_city_id,
                District.is_captured == False,
            ).order_by(District.number).limit(1)
        )
        district = next_r.scalar_one_or_none()
        if not district:
            return await self._promote_to_king(session, user, city)
        district_power = self._get_district_power(district.number, city.district_power_multiplier)
        result = await fight_district(session, user, district_power)
        if result["win"]:
            district.owner_id = user.id
            district.is_captured = True
            city.captured_districts = min(city.captured_districts + 1, city.total_districts)
            city.district_power_multiplier += random.uniform(0.02, 0.05)
            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["gang"]
            await session.flush()
            await session.refresh(city)
            if city.captured_districts >= city.total_districts:
                return await self._promote_to_king(session, user, city)
            my_districts = await self._get_my_districts_in_city(session, user.id, user.gang_city_id)
            await self._handle_attack_cd(session, user, cd_key, "gang")
            await session.flush()
            return {
                "ok": True, "win": True,
                "district_num": district.number,
                "my_districts": my_districts,
                "total": city.total_districts,
                "city_captured": city.captured_districts,
                "is_crit": result["is_crit"],
                "user_power": result["user_power"],
                "district_power": district_power,
                "extra_attacks_left": user.extra_attack_count,
            }
        else:
            my_last = await session.execute(
                select(District).where(
                    District.owner_id == user.id,
                    District.city_id == user.gang_city_id,
                    District.is_captured == True,
                ).order_by(District.number.desc()).limit(1)
            )
            lost = my_last.scalar_one_or_none()
            if lost:
                lost.owner_id = None
                lost.is_captured = False
                city.captured_districts = max(0, city.captured_districts - 1)
                await session.flush()
            my_districts = await self._get_my_districts_in_city(session, user.id, user.gang_city_id)
            if my_districts == 0:
                return await self._destroy_gang(session, user)
            await self._handle_attack_cd(session, user, cd_key, "gang")
            await session.flush()
            return {
                "ok": True, "win": False,
                "district_num": district.number,
                "district_power": district_power,
                "user_power": result["user_power"],
                "my_districts": my_districts,
                "extra_attacks_left": user.extra_attack_count,
            }

    async def gang_attack_pvp(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        if attacker.phase != "gang":
            return {"ok": False, "reason": "Только для фазы Банды"}
        if is_truce_active(attacker):
            return {"ok": False, "reason": "Во время перемирия нельзя атаковать"}
        defender = await user_repo.get_by_id(session, defender_id)
        if not defender:
            return {"ok": False, "reason": "Противник не найден"}
        if is_truce_active(defender):
            return {"ok": False, "reason": f"{defender.full_name} находится под перемирием"}
        if defender.gang_city_id != attacker.gang_city_id:
            return {"ok": False, "reason": "Противник в другом городе"}
        cd_key = cooldown_service.attack_key(attacker.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}
        result = await fight_player(session, attacker, defender)
        if result["win"]:
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["gang"]
            def_last_r = await session.execute(
                select(District).where(
                    District.owner_id == defender.id,
                    District.city_id == defender.gang_city_id,
                    District.is_captured == True,
                ).order_by(District.number.desc()).limit(1)
            )
            def_last = def_last_r.scalar_one_or_none()
            if def_last:
                def_last.owner_id = attacker.id
                from app.repositories.building_repo import building_repo
                from app.services.business_service import business_service
                await building_repo.deactivate_buildings_on_district_loss(session, defender.id, 1)
                await business_service._recalc_income(session, defender)
            def_owned = await self._get_my_districts_in_city(session, defender.id, defender.gang_city_id or 0)
            if def_owned == 0:
                await self._destroy_gang(session, defender)
            city = await city_repo.get_city(session, attacker.gang_city_id)
            if city:
                my_districts = await self._get_my_districts_in_city(session, attacker.id, attacker.gang_city_id)
                if my_districts >= city.total_districts:
                    await notify_pvp_attack(attacker, defender, True, "gang")
                    return await self._promote_to_king(session, attacker, city)
        await notify_pvp_attack(attacker, defender, result["win"], "gang")
        await self._handle_attack_cd(session, attacker, cd_key, "gang")
        await session.flush()
        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
        }
