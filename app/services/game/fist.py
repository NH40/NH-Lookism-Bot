import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.city import FistBot
from app.services.combat_service import fight_district, fight_player
from app.services.cooldown_service import cooldown_service
from app.repositories.user_repo import user_repo
from app.data.squad import ATTACK_WIN_INFLUENCE_BONUS
from app.services.game.base import GameBase, FIST_MIN_CITIES, FIST_BOT_CONFIGS
from app.services.game.utils import notify_pvp_attack


class GameFistService(GameBase):

    async def get_fist_bots(self, session: AsyncSession, user: User) -> list[FistBot]:
        result = await session.execute(
            select(FistBot).where(FistBot.challenger_id == user.id)
        )
        bots = result.scalars().all()
        if not bots:
            bots = await self._create_fist_bots(session, user)
        return list(bots)

    async def _create_fist_bots(self, session: AsyncSession, user: User) -> list[FistBot]:
        bots = []
        for cfg in FIST_BOT_CONFIGS:
            power = max(1, int(user.combat_power * cfg["ratio"]))
            bot = FistBot(
                name=cfg["name"], power_ratio=cfg["ratio"],
                base_power=power, current_power=power,
                defeat_count=0, challenger_id=user.id,
            )
            session.add(bot)
            bots.append(bot)
        await session.flush()
        return bots

    async def fist_attack_bot(
        self, session: AsyncSession, user: User, bot_id: int
    ) -> dict:
        if user.phase != "fist":
            return {"ok": False, "reason": "Только для фазы Кулака"}
        from datetime import datetime, timezone, timedelta
        result = await session.execute(
            select(FistBot).where(FistBot.id == bot_id, FistBot.challenger_id == user.id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            return {"ok": False, "reason": "Бот не найден"}
        now_dt = datetime.now(timezone.utc)
        if bot.cooldown_until and bot.cooldown_until > now_dt:
            remaining = int((bot.cooldown_until - now_dt).total_seconds())
            return {"ok": False, "reason": f"Бот восстанавливается: {cooldown_service.format_ttl(remaining)}"}
        cd_key = cooldown_service.attack_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}
        fight = await fight_district(session, user, bot.current_power)

        if fight["win"]:
            cities_gained = random.randint(2, 4)
            user.fist_cities_count += cities_gained
            user.fist_wins += 1
            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["fist"]
            bot.defeat_count += 1
            bot.cooldown_until = now_dt + timedelta(hours=1)
            new_power = int(user.combat_power * bot.power_ratio * (1 + 0.1 * bot.defeat_count))
            bot.current_power = min(new_power, int(user.combat_power * bot.power_ratio * 3.0))

            # Даём реальные районы в городах
            await self._give_fist_cities(session, user, cities_gained)
            await session.flush()

            if user.fist_wins >= 10:
                return await self._promote_to_emperor(session, user)
            await self._handle_attack_cd(session, user, cd_key, "fist")
            await session.flush()
            return {
                "ok": True, "win": True,
                "cities_gained": cities_gained, "fist_wins": user.fist_wins,
                "fist_cities": user.fist_cities_count, "is_crit": fight["is_crit"],
                "user_power": fight["user_power"], "bot_power": bot.current_power,
                "bot_name": bot.name,
            }
        else:
            cities_lost = random.randint(2, 4)
            user.fist_cities_count = max(0, user.fist_cities_count - cities_lost)
            if user.fist_cities_count < FIST_MIN_CITIES:
                await self._demote_fist_to_king(session, user)
                return {
                    "ok": True, "win": False, "demoted": True,
                    "cities_lost": cities_lost, "fist_cities": user.fist_cities_count,
                    "user_power": fight["user_power"], "bot_power": bot.current_power,
                    "bot_name": bot.name,
                    "message": (
                        f"💔 Поражение от {bot.name}!\n\n"
                        f"Потеряно городов: {cities_lost}\n"
                        f"Городов осталось: {user.fist_cities_count}\n\n"
                        f"⚠️ Вы понижены до фазы Короля!"
                    ),
                }
            await self._handle_attack_cd(session, user, cd_key, "fist")
            await session.flush()
            return {
                "ok": True, "win": False,
                "cities_lost": cities_lost, "fist_cities": user.fist_cities_count,
                "user_power": fight["user_power"], "bot_power": bot.current_power,
                "bot_name": bot.name,
            }

    async def fist_pvp_attack(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        defender = await user_repo.get_by_id(session, defender_id)
        if not defender or defender.phase != "fist":
            return {"ok": False, "reason": "Противник не найден"}
        cd_key = cooldown_service.attack_key(attacker.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}
        result = await fight_player(session, attacker, defender)
        if result["win"]:
            cities_gained = random.randint(2, 4)
            cities_lost = random.randint(2, 4)
            attacker.fist_cities_count += cities_gained
            defender.fist_cities_count = max(0, defender.fist_cities_count - cities_lost)
            attacker.fist_wins += 1
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["fist"]
            if defender.fist_cities_count < FIST_MIN_CITIES:
                await self._demote_fist_to_king(session, defender)
            if attacker.fist_wins >= 10:
                await notify_pvp_attack(attacker, defender, True, "fist")
                return await self._promote_to_emperor(session, attacker)
        else:
            cities_lost = random.randint(2, 4)
            attacker.fist_cities_count = max(0, attacker.fist_cities_count - cities_lost)
            if attacker.fist_cities_count < FIST_MIN_CITIES:
                await notify_pvp_attack(attacker, defender, False, "fist")
                await self._demote_fist_to_king(session, attacker)
                await self._handle_attack_cd(session, attacker, cd_key, "fist")
                await session.flush()
                return {
                    "ok": True, "win": False, "demoted": True,
                    "is_crit": result["is_crit"],
                    "attacker_power": result["attacker_power"],
                    "defender_power": result["defender_power"],
                    "defender_name": defender.full_name,
                }
        await notify_pvp_attack(attacker, defender, result["win"], "fist")
        await self._handle_attack_cd(session, attacker, cd_key, "fist")
        await session.flush()
        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
        }
