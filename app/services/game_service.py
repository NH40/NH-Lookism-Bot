import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.city import City, District, FistBot
from app.services.combat_service import fight_district, fight_player
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.data.squad import ATTACK_WIN_INFLUENCE_BONUS
from app.data.cities import DISTRICT_BASE_POWER

# ── КД атаки по фазам (секунды) ─────────────────────────────────────────────
ATTACK_CD: dict[str, int] = {
    "gang":     60,
    "king":     300,
    "fist":     600,
    "emperor":  600,
}

# ── Фист-боты ───────────────────────────────────────────────────────────────
FIST_BOT_CONFIGS = [
    {"name": "Рю",  "ratio": 0.80},
    {"name": "Со",  "ratio": 0.90},
    {"name": "Чан", "ratio": 1.00},
    {"name": "Пэк", "ratio": 1.10},
    {"name": "Ли",  "ratio": 1.20},
]

class GameService:

    # ════════════════════════════════════════════════════════════════════════
    # ФАЗА БАНДА
    # ════════════════════════════════════════════════════════════════════════

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

    async def choose_gang_city(
        self, session: AsyncSession, user: User, city_id: int
    ) -> dict:
        if user.gang_city_id:
            return {"ok": False, "reason": "Город уже выбран"}
        city = await city_repo.get_city(session, city_id)
        if not city or city.sector != user.sector or city.phase != "gang":
            return {"ok": False, "reason": "Город не найден"}
        if city.is_fully_captured:
            return {"ok": False, "reason": "Город уже захвачен другим игроком"}

        await city_repo.init_city_districts(session, city)
        user.gang_city_id = city_id
        await session.flush()
        return {"ok": True, "city": city.name}

    async def gang_attack(
        self, session: AsyncSession, user: User
    ) -> dict:
        if user.phase != "gang":
            return {"ok": False, "reason": "Только для фазы Банды"}
        if not user.gang_city_id:
            return {"ok": False, "reason": "Выберите город"}

        # КД
        cd_key = cooldown_service.attack_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}

        city = await city_repo.get_city(session, user.gang_city_id)
        if not city:
            return {"ok": False, "reason": "Город не найден"}

        # Следующий район
        district = await city_repo.get_next_district(session, user.gang_city_id)
        if not district:
            # Все районы захвачены — повышаем фазу
            return await self._promote_to_king(session, user, city)

        district_power = await city_repo.get_district_power(city, district.number)
        result = await fight_district(session, user, district_power)

        if result["win"]:
            await city_repo.capture_district(session, district, user.id, city)
            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["gang"]

            # Проверяем — захвачен ли весь город
            city_complete = city.captured_districts >= city.total_districts
            if city_complete:
                return await self._promote_to_king(session, user, city)

            # Выставляем КД (с учётом extra_attack_count)
            await self._handle_attack_cd(session, user, cd_key, "gang")
            await session.flush()

            return {
                "ok": True, "win": True,
                "district": district.number,
                "total": city.total_districts,
                "captured": city.captured_districts,
                "is_crit": result["is_crit"],
                "user_power": result["user_power"],
                "district_power": district_power,
            }
        else:
            # Поражение — теряем район
            lost = await city_repo.lose_district(session, user.id, user.gang_city_id)
            districts_owned = await city_repo.get_user_district_count(session, user.id)

            if districts_owned == 0:
                return await self._destroy_gang(session, user)

            await self._handle_attack_cd(session, user, cd_key, "gang")
            await session.flush()

            return {
                "ok": True, "win": False,
                "district_power": district_power,
                "user_power": result["user_power"],
                "districts_left": districts_owned,
            }

    async def gang_pvp_attack(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        defender = await user_repo.get_by_id(session, defender_id)
        if not defender:
            return {"ok": False, "reason": "Противник не найден"}

        cd_key = cooldown_service.attack_key(attacker.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "cd": ttl}

        result = await fight_player(session, attacker, defender)

        if result["win"]:
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["gang"]
            # Забираем 1 район соперника
            await city_repo.lose_district(session, defender.id, defender.gang_city_id)
            await city_repo.capture_district(
                session,
                await city_repo.get_next_district(session, attacker.gang_city_id),
                attacker.id,
                await city_repo.get_city(session, attacker.gang_city_id),
            )

        # Проверяем не уничтожен ли защитник
        def_districts = await city_repo.get_user_district_count(session, defender.id)
        if def_districts == 0:
            await self._destroy_gang(session, defender)

        await self._handle_attack_cd(session, attacker, cd_key, "gang")
        await session.flush()

        return {
            "ok": True,
            "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
        }

    # ════════════════════════════════════════════════════════════════════════
    # ФАЗА КОРОЛЬ
    # ════════════════════════════════════════════════════════════════════════

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

        # PvP если есть владелец
        if city.owner_id and city.owner_id != user.id:
            defender = await user_repo.get_by_id(session, city.owner_id)
            if defender:
                return await self._king_pvp(session, user, defender, city, cd_key)

        # Атака на бота
        from app.data.cities import KING_DISTRICT_BASE_POWER
        bot_power = int(KING_DISTRICT_BASE_POWER * city.total_districts * city.district_power_multiplier)
        result = await fight_district(session, user, bot_power)

        if result["win"]:
            districts_to_capture = random.randint(2, 8)
            # Захватываем N районов
            captured = 0
            for _ in range(districts_to_capture):
                d = await city_repo.get_next_district(session, city.id)
                if not d:
                    break
                await city_repo.capture_district(session, d, user.id, city)
                captured += 1

            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]
            user.king_cities_count = await city_repo.get_king_cities_count(session, user.id)

            if user.king_cities_count >= 10:
                return await self._promote_to_fist(session, user)

        await self._handle_attack_cd(session, user, cd_key, "king")
        await session.flush()

        return {
            "ok": True,
            "win": result["win"],
            "is_crit": result["is_crit"],
            "user_power": result["user_power"],
            "bot_power": bot_power,
            "city": city.name,
            "cities_count": user.king_cities_count,
        }

    async def _king_pvp(
        self, session: AsyncSession,
        attacker: User, defender: User,
        city: City, cd_key: str
    ) -> dict:
        result = await fight_player(session, attacker, defender)
        if result["win"]:
            # Переводим город атакующему
            city.owner_id = attacker.id
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]
            attacker.king_cities_count = await city_repo.get_king_cities_count(session, attacker.id)

            # Проверяем не уничтожен ли защитник
            def_cities = await city_repo.get_king_cities_count(session, defender.id)
            if def_cities == 0:
                await self._destroy_king(session, defender)

            if attacker.king_cities_count >= 10:
                return await self._promote_to_fist(session, attacker)

        await self._handle_attack_cd(session, attacker, cd_key, "king")
        await session.flush()

        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
            "city": city.name,
        }

    # ════════════════════════════════════════════════════════════════════════
    # ФАЗА КУЛАК
    # ════════════════════════════════════════════════════════════════════════

    async def get_fist_bots(
        self, session: AsyncSession, user: User
    ) -> list[FistBot]:
        from sqlalchemy import select
        result = await session.execute(
            select(FistBot).where(FistBot.challenger_id == user.id)
        )
        bots = result.scalars().all()
        if not bots:
            bots = await self._create_fist_bots(session, user)
        return bots

    async def _create_fist_bots(
        self, session: AsyncSession, user: User
    ) -> list[FistBot]:
        bots = []
        for cfg in FIST_BOT_CONFIGS:
            power = int(user.combat_power * cfg["ratio"])
            bot = FistBot(
                name=cfg["name"],
                power_ratio=cfg["ratio"],
                base_power=power,
                current_power=power,
                challenger_id=user.id,
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

        from sqlalchemy import select
        from datetime import datetime, timezone
        result = await session.execute(
            select(FistBot).where(
                FistBot.id == bot_id,
                FistBot.challenger_id == user.id,
            )
        )
        bot = result.scalar_one_or_none()
        if not bot:
            return {"ok": False, "reason": "Бот не найден"}

        # Проверяем КД бота
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

            # Бот уходит на КД и усиляется
            from datetime import timedelta
            bot.defeat_count += 1
            bot.cooldown_until = now_dt + timedelta(hours=1)
            bot.current_power = int(bot.base_power * (1 + 0.2 * bot.defeat_count))

            if user.fist_wins >= 10:
                return await self._promote_to_emperor(session, user)

            await self._handle_attack_cd(session, user, cd_key, "fist")
            await session.flush()

            return {
                "ok": True, "win": True,
                "cities_gained": cities_gained,
                "fist_wins": user.fist_wins,
                "fist_cities": user.fist_cities_count,
                "is_crit": fight["is_crit"],
                "user_power": fight["user_power"],
                "bot_power": bot.current_power,
                "bot_name": bot.name,
            }
        else:
            cities_lost = random.randint(2, 4)
            user.fist_cities_count = max(0, user.fist_cities_count - cities_lost)

            if user.fist_cities_count == 0:
                return await self._destroy_fist(session, user)

            await self._handle_attack_cd(session, user, cd_key, "fist")
            await session.flush()

            return {
                "ok": True, "win": False,
                "cities_lost": cities_lost,
                "fist_cities": user.fist_cities_count,
                "user_power": fight["user_power"],
                "bot_power": bot.current_power,
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
            return {"ok": False, "cd": ttl}

        result = await fight_player(session, attacker, defender)

        if result["win"]:
            cities_gained = random.randint(2, 4)
            cities_lost = random.randint(2, 4)
            attacker.fist_cities_count += cities_gained
            defender.fist_cities_count = max(0, defender.fist_cities_count - cities_lost)
            attacker.fist_wins += 1
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["fist"]

            if defender.fist_cities_count == 0:
                await self._destroy_fist(session, defender)

            if attacker.fist_wins >= 10:
                return await self._promote_to_emperor(session, attacker)
        else:
            cities_lost = random.randint(2, 4)
            attacker.fist_cities_count = max(0, attacker.fist_cities_count - cities_lost)
            if attacker.fist_cities_count == 0:
                return await self._destroy_fist(session, attacker)

        await self._handle_attack_cd(session, attacker, cd_key, "fist")
        await session.flush()

        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
        }

    # ════════════════════════════════════════════════════════════════════════
    # ВСПОМОГАТЕЛЬНЫЕ
    # ════════════════════════════════════════════════════════════════════════

    async def _handle_attack_cd(
        self, session: AsyncSession, user: User, cd_key: str, phase: str
    ) -> None:
        """Управляет КД с учётом extra_attack_count."""
        if user.extra_attack_count > 0:
            user.extra_attack_count -= 1
            # Не ставим КД
            return

        base_cd = ATTACK_CD[phase]
        # Бонус скорости от мастерства
        from app.models.skill import UserMastery
        from sqlalchemy import select
        mr = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = mr.scalar_one_or_none()
        speed_reduction = 0
        if mastery:
            speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
            speed_reduction = speed_levels.get(mastery.speed, 0)

        cd = max(10, int(base_cd * (1 - speed_reduction / 100)))
        await cooldown_service.set_cooldown(cd_key, cd)

    async def _promote_to_king(
        self, session: AsyncSession, user: User, city: City
    ) -> dict:
        user.phase = "king"
        user.king_cities_count = 1
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "king",
            "message": f"🎉 Поздравляем! Вы захватили {city.name} и стали Королём!"
        }

    async def _promote_to_fist(
        self, session: AsyncSession, user: User
    ) -> dict:
        user.phase = "fist"
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "fist",
            "message": "🎉 Вы захватили 10 городов и стали Кулаком!"
        }

    async def _promote_to_emperor(
        self, session: AsyncSession, user: User
    ) -> dict:
        user.phase = "emperor"
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "emperor",
            "message": "👑 Вы победили 10 кулаков и стали Императором!"
        }

    async def _destroy_gang(
        self, session: AsyncSession, user: User
    ) -> dict:
        """Уничтожение банды — полный сброс."""
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user)
        return {
            "ok": True, "destroyed": True,
            "message": "💀 Ваша банда уничтожена! Начинайте сначала."
        }

    async def _destroy_king(
        self, session: AsyncSession, user: User
    ) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user)
        return {"ok": True, "destroyed": True, "message": "💀 Вы потеряли все города!"}

    async def _destroy_fist(
        self, session: AsyncSession, user: User
    ) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user)
        return {"ok": True, "destroyed": True, "message": "💀 Вы потеряли все города кулака!"}


game_service = GameService()