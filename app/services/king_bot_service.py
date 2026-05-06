import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.king_bot import KingBot
from app.constants.king_bots import KING_BOT_NAMES, KING_BOT_SLOTS, KING_BOT_POWER_GROWTH
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
                bot = KingBot(
                    user_id=user.id,
                    slot=cfg["slot"],
                    name=KING_BOT_NAMES[cfg["slot"] - 1],
                    power=cfg["power"],
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
                bot.is_defeated = True
                bot.cooldown_until = now + timedelta(hours=1)
                bot.power = int(bot.power * KING_BOT_POWER_GROWTH)
                bot.districts_captured = 0

                # 1. Сначала даём город и районы
                await self._give_king_city(session, user, bot)
                await session.flush()  # ← районы записаны в БД

                user.total_wins += 1
                user.influence += 500
                coins_reward = old_power // 10
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
    
    async def _give_king_city(
        self, session: AsyncSession, user: User, bot: KingBot
    ) -> None:
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo
        from sqlalchemy import select, func

        sector = user.sector or "Н"
        districts_to_give = bot.districts_total  # сколько районов даём

        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase == "king",
            ).order_by(City.id)
        )
        all_cities = result.scalars().all()

        target_city = None
        for city in all_cities:
            my_in_city = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_in_city == 0:
                target_city = city
                break

        if not target_city and all_cities:
            target_city = all_cities[0]
        if not target_city:
            return

        # Инициализируем и флашим чтобы районы появились
        await city_repo.init_city_districts(session, target_city)
        await session.flush()

        # Берём свободные районы (не захваченные никем)
        free_r = await session.execute(
            select(District).where(
                District.city_id == target_city.id,
                District.is_captured == False,
            ).order_by(District.number).limit(districts_to_give)
        )
        free_districts = free_r.scalars().all()

        # Если свободных не хватает — добираем любые не наши
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
            free_districts = list(free_districts) + list(extra_r.scalars().all())

        captured = 0
        for d in free_districts:
            d.owner_id = user.id
            d.is_captured = True
            captured += 1

        # Синхронизируем счётчик города
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