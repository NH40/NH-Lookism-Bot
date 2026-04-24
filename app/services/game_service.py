import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.city import City, District, FistBot
from app.services.combat_service import fight_district, fight_player
from app.services.cooldown_service import cooldown_service
from app.repositories.city_repo import city_repo
from app.repositories.user_repo import user_repo
from app.data.squad import ATTACK_WIN_INFLUENCE_BONUS

ATTACK_CD: dict[str, int] = {
    "gang":    60,
    "king":    300,
    "fist":    600,
    "emperor": 600,
}

FIST_BOT_CONFIGS = [
    {"name": "Рю",  "ratio": 0.80},
    {"name": "Со",  "ratio": 0.90},
    {"name": "Чан", "ratio": 1.00},
    {"name": "Пэк", "ratio": 1.10},
    {"name": "Ли",  "ratio": 1.20},
]

# Мощь районов на этапе банды
GANG_DISTRICT_BASE_POWER = 10  # первый район = 10 мощи


class GameService:

    # ── Вспомогательные ─────────────────────────────────────────────────────

    def _get_max_extra_attacks(self, user: User) -> int:
        """
        Максимальное количество ДОПОЛНИТЕЛЬНЫХ атак за один КД.
        Возвращает количество которое восстанавливается после КД.
        """
        if not user.double_attack:
            return 0
        # Оба источника: сет монстра + путь монстра с double_train
        if user.skill_path == "monster" and user.double_train:
            return 2  # итого 3 атаки за КД
        return 1  # итого 2 атаки за КД


    async def _handle_attack_cd(
        self, session: AsyncSession, user: User, cd_key: str, phase: str
    ) -> None:
        """
        Логика КД и доп атак:
        - Если есть запас доп атак → тратим одну, КД не ставим
        - Когда запас исчерпан → ставим КД, восстанавливаем запас
        """
        if user.extra_attack_count > 0:
            # Есть ещё атаки в запасе — не ставим КД
            user.extra_attack_count -= 1
            return

        # Запас исчерпан — ставим КД
        base_cd = ATTACK_CD[phase]

        from app.models.skill import UserMastery
        mr = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = mr.scalar_one_or_none()
        speed_pct = 0
        if mastery:
            speed_pct = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(mastery.speed, 0)

        # Сет "flow" даёт -15% ко всем КД
        from app.repositories.title_repo import title_repo
        has_flow = await title_repo.has_set(session, user.id, "flow")
        if has_flow:
            speed_pct = min(80, speed_pct + 15)

        cd = max(10, int(base_cd * (1 - speed_pct / 100)))
        await cooldown_service.set_cooldown(cd_key, cd)

        # Восстанавливаем запас доп атак для следующего КД
        user.extra_attack_count = self._get_max_extra_attacks(user)

    async def _get_my_districts_in_city(
        self, session: AsyncSession, user_id: int, city_id: int
    ) -> int:
        result = await session.scalar(
            select(func.count(District.id)).where(
                District.owner_id == user_id,
                District.city_id == city_id,
                District.is_captured == True,
            )
        )
        return result or 0

    # ── ФАЗА БАНДА ──────────────────────────────────────────────────────────

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
            return {"ok": False, "reason": "Город уже полностью захвачен"}
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

        cd_key = cooldown_service.attack_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД: {cooldown_service.format_ttl(ttl)}", "cd": ttl}

        city = await city_repo.get_city(session, user.gang_city_id)
        if not city:
            return {"ok": False, "reason": "Город не найден"}

        await city_repo.init_city_districts(session, city)

        # Следующий незахваченный район
        district = await city_repo.get_next_district(session, user.gang_city_id)
        if not district:
            return await self._promote_to_king(session, user, city)

        # Мощь района: base=10, каждый следующий чуть сильнее
        district_power = max(10, int(
            GANG_DISTRICT_BASE_POWER
            * (district.number ** 0.5)
            * city.district_power_multiplier
        ))

        result = await fight_district(session, user, district_power)

        if result["win"]:
            await city_repo.capture_district(session, district, user.id, city)
            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["gang"]

            # Обновляем city
            await session.refresh(city)
            if city.captured_districts >= city.total_districts:
                return await self._promote_to_king(session, user, city)

            await self._handle_attack_cd(session, user, cd_key, "gang")
            await session.flush()

            owned = await self._get_my_districts_in_city(
                session, user.id, user.gang_city_id
            )

            return {
                "ok": True, "win": True,
                "district_num": district.number,
                "total": city.total_districts,
                "city_captured": city.captured_districts,
                "owned_by_me": owned,
                "is_crit": result["is_crit"],
                "user_power": result["user_power"],
                "district_power": district_power,
                "extra_attacks_left": user.extra_attack_count,
            }
        else:
            # Теряем наш последний район в этом городе
            last_r = await session.execute(
                select(District).where(
                    District.owner_id == user.id,
                    District.city_id == user.gang_city_id,
                    District.is_captured == True,
                ).order_by(District.number.desc()).limit(1)
            )
            last = last_r.scalar_one_or_none()
            if last:
                last.owner_id = None
                last.is_captured = False
                city.captured_districts = max(0, city.captured_districts - 1)

            owned = await self._get_my_districts_in_city(
                session, user.id, user.gang_city_id
            )

            if owned == 0:
                return await self._destroy_gang(session, user)

            await self._handle_attack_cd(session, user, cd_key, "gang")
            await session.flush()

            return {
                "ok": True, "win": False,
                "district_power": district_power,
                "user_power": result["user_power"],
                "districts_left": owned,
                "extra_attacks_left": user.extra_attack_count,
            }

    async def gang_pvp_attack(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        defender = await user_repo.get_by_id(session, defender_id)
        if not defender:
            return {"ok": False, "reason": "Противник не найден"}
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

            # Забираем 1 район соперника
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
                # Районы просто переходят к атакующему

            # Проверяем не уничтожен ли защитник
            def_owned = await self._get_my_districts_in_city(
                session, defender.id, defender.gang_city_id or 0
            )
            if def_owned == 0:
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

    # ── ФАЗА КОРОЛЬ ─────────────────────────────────────────────────────────

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
            if defender and defender.phase == "king":
                return await self._king_pvp(session, user, defender, city, cd_key)

        # Бот: мощь адаптивная
        from app.data.cities import KING_DISTRICT_BASE_POWER
        # Формула: кол-во зданий × мощь района × % от силы атакующего
        from app.models.building import UserBuilding
        buildings_count = await session.scalar(
            select(func.count(UserBuilding.id)).where(
                UserBuilding.city_id == city_id,
                UserBuilding.is_active == True,
            )
        ) or 0

        if buildings_count > 0:
            bot_power = int(
                buildings_count * 50  # мощь здания
                * city.district_power_multiplier
                * 0.7  # 70% от потенциала
            )
        else:
            bot_power = int(
                KING_DISTRICT_BASE_POWER
                * city.total_districts
                * city.district_power_multiplier
            )

        result = await fight_district(session, user, bot_power)

        if result["win"]:
            districts_gained = random.randint(2, 8)
            captured = 0
            await city_repo.init_city_districts(session, city)
            for _ in range(districts_gained):
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
            "districts_gained": districts_gained if result["win"] else 0,
        }

    async def _king_pvp(
        self, session: AsyncSession,
        attacker: User, defender: User,
        city: City, cd_key: str
    ) -> dict:
        result = await fight_player(session, attacker, defender)
        if result["win"]:
            city.owner_id = attacker.id
            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]
            attacker.king_cities_count = await city_repo.get_king_cities_count(
                session, attacker.id
            )
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

    # ── ФАЗА КУЛАК ──────────────────────────────────────────────────────────

    async def get_fist_bots(
        self, session: AsyncSession, user: User
    ) -> list[FistBot]:
        result = await session.execute(
            select(FistBot).where(FistBot.challenger_id == user.id)
        )
        bots = result.scalars().all()
        if not bots:
            bots = await self._create_fist_bots(session, user)
        return list(bots)

    async def _create_fist_bots(
        self, session: AsyncSession, user: User
    ) -> list[FistBot]:
        bots = []
        for cfg in FIST_BOT_CONFIGS:
            power = max(1, int(user.combat_power * cfg["ratio"]))
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

        from datetime import datetime, timezone, timedelta
        result = await session.execute(
            select(FistBot).where(
                FistBot.id == bot_id,
                FistBot.challenger_id == user.id,
            )
        )
        bot = result.scalar_one_or_none()
        if not bot:
            return {"ok": False, "reason": "Бот не найден"}

        now_dt = datetime.now(timezone.utc)
        if bot.cooldown_until and bot.cooldown_until > now_dt:
            remaining = int((bot.cooldown_until - now_dt).total_seconds())
            return {
                "ok": False,
                "reason": f"Бот восстанавливается: {cooldown_service.format_ttl(remaining)}"
            }

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
            # После поражения бот становится на 20% сильнее победителя
            bot.current_power = int(user.combat_power * bot.power_ratio * (1 + 0.2 * bot.defeat_count))

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

    # ── Переходы и уничтожение ──────────────────────────────────────────────

    async def _promote_to_king(
        self, session: AsyncSession, user: User, city: City
    ) -> dict:
        user.phase = "king"
        user.king_cities_count = 1
        # Восстанавливаем счётчик атак для новой фазы
        user.extra_attack_count = self._get_max_extra_attacks(user)
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "king",
            "message": f"🎉 Вы захватили {city.name} и стали Королём!\nТеперь захватите 10 городов."
        }

    async def _promote_to_fist(
        self, session: AsyncSession, user: User
    ) -> dict:
        user.phase = "fist"
        user.extra_attack_count = self._get_max_extra_attacks(user)
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "fist",
            "message": "🎉 Вы захватили 10 городов и стали Кулаком!\nПобедите 10 кулаков."
        }

    async def _promote_to_emperor(
        self, session: AsyncSession, user: User
    ) -> dict:
        user.phase = "emperor"
        user.extra_attack_count = 0
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "emperor",
            "message": "👑 Вы победили 10 кулаков и стали Императором!"
        }

    async def _destroy_gang(self, session: AsyncSession, user: User) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user)
        return {
            "ok": True, "destroyed": True,
            "message": "💀 Ваша банда уничтожена! Начинайте сначала."
        }

    async def _destroy_king(self, session: AsyncSession, user: User) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user)
        return {"ok": True, "destroyed": True, "message": "💀 Вы потеряли все города!"}

    async def _destroy_fist(self, session: AsyncSession, user: User) -> dict:
        from app.services.prestige_service import prestige_service
        await prestige_service._reset_progress(session, user)
        return {"ok": True, "destroyed": True, "message": "💀 Вы потеряли все города кулака!"}


game_service = GameService()