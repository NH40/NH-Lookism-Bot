import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.king_bot import KingBot
from app.constants.king_bots import KING_BOT_NAMES, KING_BOT_SLOTS, KING_BOT_POWER_GROWTH, KING_BOT_MIN_POWER
from app.services.cooldown_service import cooldown_service
from app.services.game.base import GameBase


class KingBotService(GameBase):

    async def get_or_create_bots(
        self, session: AsyncSession, user: User
    ) -> list[KingBot]:
        result = await session.execute(
            select(KingBot).where(KingBot.user_id == user.id).order_by(KingBot.slot)
        )
        bots = result.scalars().all()

        existing_slots = {b.slot for b in bots}
        for cfg in KING_BOT_SLOTS:
            if cfg["slot"] not in existing_slots:
                power = max(
                    KING_BOT_MIN_POWER,
                    int(user.combat_power * cfg["power_ratio"]),
                )
                bot = KingBot(
                    user_id=user.id,
                    slot=cfg["slot"],
                    name=KING_BOT_NAMES[cfg["slot"] - 1],
                    power=power,
                    districts_total=cfg["districts"],
                    districts_captured=0,
                )
                session.add(bot)

        await session.flush()

        result = await session.execute(
            select(KingBot).where(KingBot.user_id == user.id).order_by(KingBot.slot)
        )
        return result.scalars().all()

    async def attack_bot(
        self, session: AsyncSession, user: User, bot_id: int
    ) -> dict:
        result = await session.execute(
            select(KingBot).where(
                KingBot.id == bot_id,
                KingBot.user_id == user.id,
            )
        )
        bot = result.scalar_one_or_none()
        if not bot:
            return {"ok": False, "reason": "Бот не найден"}

        now = datetime.now(timezone.utc)

        # КД бота (1 час после победы)
        if bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now:
            remaining = int((bot.cooldown_until - now).total_seconds())
            return {
                "ok": False,
                "reason": f"Бот восстанавливается: {cooldown_service.format_ttl(remaining)}",
                "cd": remaining,
            }

        # Сбрасываем флаг после КД
        if bot.is_defeated and (not bot.cooldown_until or bot.cooldown_until <= now):
            bot.is_defeated = False
            bot.districts_captured = 0

        # ── Общий КД атаки (тот же что у городов) ──────────────────────────
        cd_key = cooldown_service.attack_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {
                "ok": False,
                "reason": f"КД атаки: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        # Бой
        user_power = user.combat_power
        win = user_power >= bot.power

        if win:
            districts_per_attack = random.randint(2, 6)
            remaining_districts = bot.districts_total - bot.districts_captured
            gained = min(districts_per_attack, remaining_districts)
            bot.districts_captured += gained

            fully_captured = bot.districts_captured >= bot.districts_total

            coins_reward = 0
            if fully_captured:
                old_power = bot.power
                districts_to_give = bot.districts_total  # ← сохраняем ДО любых изменений

                bot.is_defeated = True
                bot.cooldown_until = now + timedelta(hours=1)
                bot.power = int(bot.power * KING_BOT_POWER_GROWTH)
                bot.districts_captured = 0

                # Передаём districts_to_give явно
                await self._give_king_city(session, user, bot, districts_to_give)
                await session.flush()

                user.total_wins += 1
                user.influence += 500
                coins_reward = min(old_power // 10, 4_000_000)
                user.nh_coins += coins_reward

                # 2. Теперь считаем — районы уже есть
                user.king_cities_count = await self._count_my_king_cities(session, user.id)

                # 3. КД
                await self._handle_attack_cd(session, user, cd_key, "king")
                await session.flush()

                # 4. Проверяем повышение
                if user.king_cities_count >= 10:
                    return await self._promote_to_fist(session, user)

                return {
                    "ok": True,
                    "win": True,
                    "gained": gained,
                    "captured": bot.districts_captured,
                    "total": bot.districts_total,
                    "fully_captured": True,
                    "bot_name": bot.name,
                    "user_power": user_power,
                    "bot_power": bot.power,
                    "coins_reward": coins_reward,
                    "cities_count": user.king_cities_count,
                    "extra_attacks_left": user.extra_attack_count,
                }

            # ── Используем общий _handle_attack_cd — он обрабатывает extra_attack ──
            await self._handle_attack_cd(session, user, cd_key, "king")
            await session.flush()

            return {
                "ok": True,
                "win": True,
                "gained": gained,
                "captured": bot.districts_captured,
                "total": bot.districts_total,
                "fully_captured": fully_captured,
                "bot_name": bot.name,
                "user_power": user_power,
                "bot_power": bot.power,
                "coins_reward": coins_reward,
                "cities_count": user.king_cities_count,
                "extra_attacks_left": user.extra_attack_count,
            }
        else:
            # При поражении тоже используем общий КД
            await self._handle_attack_cd(session, user, cd_key, "king")
            await session.flush()

            return {
                "ok": True,
                "win": False,
                "captured": bot.districts_captured,
                "total": bot.districts_total,
                "fully_captured": False,
                "bot_name": bot.name,
                "user_power": user_power,
                "bot_power": bot.power,
                "extra_attacks_left": user.extra_attack_count,
            }
    
    async def _find_or_create_king_city(
        self, session: AsyncSession, user: User,
        districts_to_give: int, sector: str,
    ):
        """Возвращает город где у игрока 0 районов. Создаёт новый если таких нет."""
        from app.models.city import City, District
        from sqlalchemy import select, func

        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == "king",
            ).order_by(City.id)
        )
        all_cities = result.scalars().all()

        # 1. Ищем город подходящего размера где игрока ещё нет
        for city in all_cities:
            if city.total_districts < districts_to_give:
                continue
            my_in_city = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_in_city == 0:
                return city

        # 2. Любой город (любого размера) где игрока ещё нет
        for city in sorted(all_cities, key=lambda c: abs(c.total_districts - districts_to_give)):
            my_in_city = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_in_city == 0:
                return city

        # 3. Свободного города нет — создаём новый
        return await self._create_king_city(session, districts_to_give, sector, all_cities)

    async def _create_king_city(
        self, session: AsyncSession,
        districts_to_give: int, sector: str, existing_cities: list,
    ):
        from app.models.city import City
        from app.data.cities import CITY_NAMES_BY_SECTOR, CITY_TYPE_DISTRICTS

        # Выбираем type_id — ближайший сверху по кол-ву районов
        type_id = max(CITY_TYPE_DISTRICTS.keys())
        for tid, total in sorted(CITY_TYPE_DISTRICTS.items()):
            if total >= districts_to_give:
                type_id = tid
                break
        total_districts = CITY_TYPE_DISTRICTS[type_id]

        used_names = {c.name for c in existing_cities}
        all_names = CITY_NAMES_BY_SECTOR.get(sector, [])
        available = [n for n in all_names if n not in used_names]
        name = random.choice(available) if available else f"Новый квартал {sector}-{len(existing_cities) + 1}"

        new_city = City(
            sector=sector,
            phase="king",
            type_id=type_id,
            name=name,
            total_districts=total_districts,
            captured_districts=0,
            is_fully_captured=False,
            district_power_multiplier=1.0,
        )
        session.add(new_city)
        await session.flush()
        return new_city

    async def _give_king_city(
        self, session: AsyncSession, user: User, bot: KingBot,
        districts_to_give: int = None,
    ) -> None:
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo
        from sqlalchemy import select, func

        if districts_to_give is None:
            districts_to_give = bot.districts_total

        sector = user.sector or "Н"

        target_city = await self._find_or_create_king_city(
            session, user, districts_to_give, sector
        )
        if not target_city:
            return

        await city_repo.init_city_districts(session, target_city)
        await session.flush()

        # Берём свободные районы
        free_r = await session.execute(
            select(District).where(
                District.city_id == target_city.id,
                District.is_captured == False,
            ).order_by(District.number).limit(districts_to_give)
        )
        free_districts = list(free_r.scalars().all())

        # Если свободных не хватает — добираем из чужих
        if len(free_districts) < districts_to_give:
            need_more = districts_to_give - len(free_districts)
            free_ids = {d.id for d in free_districts}
            extra_r = await session.execute(
                select(District).where(
                    District.city_id == target_city.id,
                    District.owner_id != user.id,
                    District.id.not_in(free_ids),
                ).order_by(District.number).limit(need_more)
            )
            free_districts += list(extra_r.scalars().all())

        for d in free_districts:
            d.owner_id = user.id
            d.is_captured = True

        real_captured = await session.scalar(
            select(func.count(District.id)).where(
                District.city_id == target_city.id,
                District.is_captured == True,
            )
        ) or 0
        target_city.captured_districts = min(real_captured, target_city.total_districts)

        if not target_city.owner_id:
            target_city.owner_id = user.id

        await session.flush()

    def format_bot_status(self, bot: KingBot, user_power: int = 0) -> str:
        now = datetime.now(timezone.utc)
        if bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now:
            remaining = int((bot.cooldown_until - now).total_seconds())
            return f"⏳ КД: {cooldown_service.format_ttl(remaining)}"
        pct = int(bot.districts_captured / bot.districts_total * 100) if bot.districts_total > 0 else 0
        can = "✅" if user_power >= bot.power else "❌"
        return f"{can} {bot.districts_captured}/{bot.districts_total}р ({pct}%)"


king_bot_service = KingBotService()