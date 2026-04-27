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
from app.utils.formatters import fmt_num

ATTACK_CD: dict[str, int] = {
    "gang":    60,
    "king":    300,
    "fist":    600,
    "emperor": 1000,
}

FIST_BOT_CONFIGS = [
    {"name": "Рю",  "ratio": 0.80},
    {"name": "Со",  "ratio": 0.90},
    {"name": "Чан", "ratio": 1.00},
    {"name": "Пэк", "ratio": 1.10},
    {"name": "Ли",  "ratio": 1.20},
]

# Минимум городов для фазы кулака
FIST_MIN_CITIES = 10


async def _notify_pvp_attack(
    attacker: User, defender: User,
    win: bool, phase: str
) -> None:
    try:
        if not defender.notifications_enabled:
            return
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        phase_names = {"gang": "банды", "king": "королей", "fist": "кулаков"}
        phase_str = phase_names.get(phase, "")
        if win:
            text = (
                f"⚔️ <b>На вас напали!</b>\n\n"
                f"<b>{attacker.full_name}</b> атаковал вас "
                f"в PvP {phase_str} и победил!\n\n"
                f"💪 Его мощь: {fmt_num(attacker.combat_power)}\n"
                f"⚔️ Ваша мощь: {fmt_num(defender.combat_power)}"
            )
        else:
            text = (
                f"🛡 <b>Атака отражена!</b>\n\n"
                f"<b>{attacker.full_name}</b> атаковал вас "
                f"в PvP {phase_str} и проиграл!\n\n"
                f"💪 Его мощь: {fmt_num(attacker.combat_power)}\n"
                f"⚔️ Ваша мощь: {fmt_num(defender.combat_power)}"
            )
        await bot.send_message(defender.tg_id, text, parse_mode="HTML")
    except Exception:
        pass


class GameService:

    def _get_max_extra_attacks(self, user: User) -> int:
        if not user.double_attack:
            return 0
        return 1

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
        user.extra_attack_count = await self._get_max_extra_attacks_async(
            session, user
        )

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

    def _get_district_power(self, district_number: int, multiplier: float) -> int:
        return max(10, int(10 * (district_number ** 0.6) * multiplier))

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

    async def _demote_fist_to_king(
        self, session: AsyncSession, user: User
    ) -> None:
        """Понижаем кулака до короля если городов < 10."""
        user.phase = "king"
        user.fist_cities_count = 0
        user.king_cities_count = await self._count_my_king_cities(session, user.id)
        user.extra_attack_count = await self._get_max_extra_attacks_async(
            session, user
        )
        await session.flush()

        # Уведомляем
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
            return {"ok": False, "reason": "Город уже выбран — завоюйте его до конца!"}
        city = await city_repo.get_city(session, city_id)
        if not city or city.sector != user.sector or city.phase != "gang":
            return {"ok": False, "reason": "Город не найден"}
        await city_repo.init_city_districts(session, city)
        user.gang_city_id = city_id
        await session.flush()
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

        my_districts = await self._get_my_districts_in_city(
            session, user.id, user.gang_city_id
        )

        next_bot_r = await session.execute(
            select(District).where(
                District.city_id == user.gang_city_id,
                District.is_captured == False,
            ).order_by(District.number).limit(1)
        )
        next_bot = next_bot_r.scalar_one_or_none()

        bot_district_power = None
        if next_bot:
            bot_district_power = self._get_district_power(
                next_bot.number, city.district_power_multiplier
            )

        rivals = await user_repo.get_players_in_city(
            session, user.gang_city_id, user.id
        )

        rival_info = []
        for rival in rivals:
            rival_districts = await self._get_my_districts_in_city(
                session, rival.id, user.gang_city_id
            )
            if rival_districts > 0:
                rival_info.append({
                    "id": rival.id,
                    "name": rival.full_name,
                    "combat_power": rival.combat_power,
                    "districts": rival_districts,
                })

        return {
            "ok": True,
            "city": city,
            "my_districts": my_districts,
            "total_districts": city.total_districts,
            "next_bot_district": next_bot,
            "bot_district_power": bot_district_power,
            "rivals": rival_info,
            "city_fully_captured": city.is_fully_captured,
        }

    async def gang_attack_bot(
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

        next_r = await session.execute(
            select(District).where(
                District.city_id == user.gang_city_id,
                District.is_captured == False,
            ).order_by(District.number).limit(1)
        )
        district = next_r.scalar_one_or_none()

        if not district:
            return await self._promote_to_king(session, user, city)

        district_power = self._get_district_power(
            district.number, city.district_power_multiplier
        )
        result = await fight_district(session, user, district_power)

        if result["win"]:
            district.owner_id = user.id
            district.is_captured = True
            city.captured_districts = min(
                city.captured_districts + 1, city.total_districts
            )
            city.district_power_multiplier += random.uniform(0.02, 0.05)
            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["gang"]

            await session.flush()
            await session.refresh(city)

            if city.captured_districts >= city.total_districts:
                return await self._promote_to_king(session, user, city)

            my_districts = await self._get_my_districts_in_city(
                session, user.id, user.gang_city_id
            )
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

            my_districts = await self._get_my_districts_in_city(
                session, user.id, user.gang_city_id
            )

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

            def_owned = await self._get_my_districts_in_city(
                session, defender.id, defender.gang_city_id or 0
            )
            if def_owned == 0:
                await self._destroy_gang(session, defender)

            city = await city_repo.get_city(session, attacker.gang_city_id)
            if city:
                my_districts = await self._get_my_districts_in_city(
                    session, attacker.id, attacker.gang_city_id
                )
                if my_districts >= city.total_districts:
                    await _notify_pvp_attack(attacker, defender, True, "gang")
                    return await self._promote_to_king(session, attacker, city)

        await _notify_pvp_attack(attacker, defender, result["win"], "gang")
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

    async def gang_attack(self, session: AsyncSession, user: User) -> dict:
        return await self.gang_attack_bot(session, user)

    async def gang_pvp_attack(
        self, session: AsyncSession, attacker: User, defender_id: int
    ) -> dict:
        return await self.gang_attack_pvp(session, attacker, defender_id)

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

        dominant_id = await self._get_city_dominant_player(
            session, city_id, user.id
        )
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
            bot_power = int(
                buildings_count * 50 * city.district_power_multiplier * 0.7
            )
        else:
            bot_power = int(
                KING_DISTRICT_BASE_POWER
                * city.total_districts
                * city.district_power_multiplier
            )
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

            # Синхронизируем captured_districts с реальными данными
            real_captured = await session.scalar(
                select(func.count(District.id)).where(
                    District.city_id == city_id,
                    District.is_captured == True,
                )
            ) or 0
            city.captured_districts = min(real_captured, city.total_districts)

            if districts_gained > 0 and not city.owner_id:
                city.owner_id = user.id

            user.total_wins += 1
            user.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]

            my_in_city = await self._get_my_districts_in_city(
                session, user.id, city_id
            )
            my_cities_count = await self._count_my_king_cities(session, user.id)
            user.king_cities_count = my_cities_count

            await session.flush()

            if my_cities_count >= 10:
                return await self._promote_to_fist(session, user)

            await self._handle_attack_cd(session, user, cd_key, "king")
            await session.flush()

            return {
                "ok": True, "win": True,
                "is_crit": result["is_crit"],
                "user_power": result["user_power"],
                "bot_power": bot_power,
                "city": city.name,
                "cities_count": my_cities_count,
                "districts_gained": districts_gained,
                "my_in_city": my_in_city,
                "city_captured": city.captured_districts,
                "city_total": city.total_districts,
            }
        else:
            my_in_city = await self._get_my_districts_in_city(
                session, user.id, city_id
            )
            await self._handle_attack_cd(session, user, cd_key, "king")
            await session.flush()

            return {
                "ok": True, "win": False,
                "is_crit": result["is_crit"],
                "user_power": result["user_power"],
                "bot_power": bot_power,
                "city": city.name,
                "cities_count": user.king_cities_count,
                "districts_gained": 0,
                "my_in_city": my_in_city,
                "city_captured": city.captured_districts,
                "city_total": city.total_districts,
            }

    async def _king_pvp(
        self, session: AsyncSession,
        attacker: User, defender: User,
        city: City, cd_key: str
    ) -> dict:
        result = await fight_player(session, attacker, defender)

        if result["win"]:
            # Забираем только 2-8 районов, не все
            defender_districts_r = await session.execute(
                select(District).where(
                    District.city_id == city.id,
                    District.owner_id == defender.id,
                    District.is_captured == True,
                ).order_by(District.number.desc())
                .limit(random.randint(2, 8))
            )
            defender_districts = defender_districts_r.scalars().all()
            taken = 0
            for d in defender_districts:
                d.owner_id = attacker.id
                taken += 1

            if taken > 0:
                city.owner_id = attacker.id

            attacker.total_wins += 1
            attacker.influence += ATTACK_WIN_INFLUENCE_BONUS["king"]

            my_cities_count = await self._count_my_king_cities(session, attacker.id)
            attacker.king_cities_count = my_cities_count

            # Проверяем защитника — если городов стало 0, уничтожаем
            def_cities = await self._count_my_king_cities(session, defender.id)
            defender.king_cities_count = def_cities
            if def_cities == 0:
                await self._destroy_king(session, defender)

            await _notify_pvp_attack(attacker, defender, True, "king")
            await session.flush()

            if my_cities_count >= 10:
                return await self._promote_to_fist(session, attacker)

            my_in_city = await self._get_my_districts_in_city(
                session, attacker.id, city.id
            )
            await self._handle_attack_cd(session, attacker, cd_key, "king")
            await session.flush()

            return {
                "ok": True, "win": True,
                "is_crit": result["is_crit"],
                "attacker_power": result["attacker_power"],
                "defender_power": result["defender_power"],
                "defender_name": defender.full_name,
                "city": city.name,
                "districts_taken": taken,
                "my_in_city": my_in_city,
                "cities_count": my_cities_count,
            }
        else:
            await _notify_pvp_attack(attacker, defender, False, "king")
            await self._handle_attack_cd(session, attacker, cd_key, "king")
            await session.flush()

            return {
                "ok": True, "win": False,
                "is_crit": result["is_crit"],
                "attacker_power": result["attacker_power"],
                "defender_power": result["defender_power"],
                "defender_name": defender.full_name,
                "city": city.name,
                "districts_taken": 0,
                "my_in_city": await self._get_my_districts_in_city(
                    session, attacker.id, city.id
                ),
                "cities_count": attacker.king_cities_count,
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
            bot.current_power = int(
                user.combat_power * bot.power_ratio * (1 + 0.2 * bot.defeat_count)
            )

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

            if user.fist_cities_count < FIST_MIN_CITIES:
                # Не уничтожаем — понижаем до короля
                await self._demote_fist_to_king(session, user)
                return {
                    "ok": True, "win": False,
                    "demoted": True,
                    "cities_lost": cities_lost,
                    "fist_cities": user.fist_cities_count,
                    "user_power": fight["user_power"],
                    "bot_power": bot.current_power,
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

            # Защитник — понижаем до короля если городов < 10
            if defender.fist_cities_count < FIST_MIN_CITIES:
                await self._demote_fist_to_king(session, defender)

            if attacker.fist_wins >= 10:
                await _notify_pvp_attack(attacker, defender, True, "fist")
                return await self._promote_to_emperor(session, attacker)

        else:
            cities_lost = random.randint(2, 4)
            attacker.fist_cities_count = max(0, attacker.fist_cities_count - cities_lost)

            # Атакующий — понижаем до короля если городов < 10
            if attacker.fist_cities_count < FIST_MIN_CITIES:
                await _notify_pvp_attack(attacker, defender, False, "fist")
                await self._demote_fist_to_king(session, attacker)
                await self._handle_attack_cd(session, attacker, cd_key, "fist")
                await session.flush()
                return {
                    "ok": True, "win": False,
                    "demoted": True,
                    "is_crit": result["is_crit"],
                    "attacker_power": result["attacker_power"],
                    "defender_power": result["defender_power"],
                    "defender_name": defender.full_name,
                }

        await _notify_pvp_attack(attacker, defender, result["win"], "fist")
        await self._handle_attack_cd(session, attacker, cd_key, "fist")
        await session.flush()

        return {
            "ok": True, "win": result["win"],
            "is_crit": result["is_crit"],
            "attacker_power": result["attacker_power"],
            "defender_power": result["defender_power"],
            "defender_name": defender.full_name,
        }

    # ── ПЕРЕХОДЫ И УНИЧТОЖЕНИЕ ──────────────────────────────────────────────

    async def _promote_to_king(
        self, session: AsyncSession, user: User, city: City
    ) -> dict:
        user.phase = "king"
        user.king_cities_count = 1
        city.owner_id = user.id
        city.is_fully_captured = True
        user.extra_attack_count = await self._get_max_extra_attacks_async(
            session, user
        )
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "king",
            "message": (
                f"🎉 Вы захватили <b>{city.name}</b> и стали Королём!\n\n"
                f"Захватите районы в 10 городах чтобы стать Кулаком."
            )
        }

    async def _promote_to_fist(
        self, session: AsyncSession, user: User
    ) -> dict:
        user.phase = "fist"
        user.fist_cities_count = FIST_MIN_CITIES
        user.extra_attack_count = await self._get_max_extra_attacks_async(
            session, user
        )
        await session.flush()
        return {
            "ok": True, "promoted": True,
            "new_phase": "fist",
            "message": (
                "✊ Вы набрали районы в 10 городах и стали Кулаком!\n\n"
                "Победите 10 кулаков чтобы стать Императором."
            )
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
        return {
            "ok": True, "destroyed": True,
            "message": "💀 Вы потеряли все города!"
        }

    async def _destroy_fist(self, session: AsyncSession, user: User) -> dict:
        """Устарело — используем _demote_fist_to_king."""
        await self._demote_fist_to_king(session, user)
        return {
            "ok": True, "destroyed": True,
            "message": "💀 Вы потеряли слишком много городов и понижены до Короля!"
        }


game_service = GameService()