import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.king_bot import KingBot
from app.constants.king_bots import KING_BOT_NAMES, KING_BOT_SLOTS, KING_BOT_POWER_GROWTH
from app.services.cooldown_service import cooldown_service


class KingBotService:

    async def get_or_create_bots(
        self, session: AsyncSession, user: User
    ) -> list[KingBot]:
        result = await session.execute(
            select(KingBot).where(
                KingBot.user_id == user.id
            ).order_by(KingBot.slot)
        )
        bots = result.scalars().all()

        # Создаём недостающих ботов
        existing_slots = {b.slot for b in bots}
        new_bots = []
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
                new_bots.append(bot)

        if new_bots:
            await session.flush()
            result = await session.execute(
                select(KingBot).where(
                    KingBot.user_id == user.id
                ).order_by(KingBot.slot)
            )
            bots = result.scalars().all()

        return list(bots)

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

        # Проверяем КД
        if bot.cooldown_until and bot.cooldown_until > now:
            remaining = int((bot.cooldown_until - now).total_seconds())
            return {
                "ok": False,
                "reason": f"Бот восстанавливается: {cooldown_service.format_ttl(remaining)}",
                "cd": remaining,
            }

        # Сбрасываем флаг победы если КД прошёл
        if bot.is_defeated and (not bot.cooldown_until or bot.cooldown_until <= now):
            bot.is_defeated = False
            bot.districts_captured = 0

        # Проверяем КД атаки игрока
        from app.services.cooldown_service import cooldown_service
        cd_key = f"king_bot_attack:{user.id}"
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
            # Захватываем районы
            cfg = KING_BOT_SLOTS[bot.slot - 1]
            districts_per_attack = random.randint(2, 6)
            remaining_districts = bot.districts_total - bot.districts_captured
            gained = min(districts_per_attack, remaining_districts)
            bot.districts_captured += gained

            fully_captured = bot.districts_captured >= bot.districts_total

            if fully_captured:
                # Бот побеждён — ставим КД и усиливаем
                bot.is_defeated = True
                bot.cooldown_until = now + timedelta(hours=1)
                bot.power = int(bot.power * KING_BOT_POWER_GROWTH)
                bot.districts_captured = 0

                user.total_wins += 1
                user.influence += 500
                user.nh_coins += bot.power // 10

            # КД атаки игрока
            from app.repositories.city_repo import city_repo as cr
            attack_cd = self._get_attack_cd(user)
            await cooldown_service.set_cooldown(cd_key, attack_cd)
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
                "coins_reward": bot.power // 10 if fully_captured else 0,
            }
        else:
            # КД атаки игрока
            attack_cd = self._get_attack_cd(user)
            await cooldown_service.set_cooldown(cd_key, attack_cd)
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
            }

    def _get_attack_cd(self, user: User) -> int:
        """КД атаки на бота (в секундах) — такой же как обычная атака."""
        return 3600  # 1 час

    def format_bot_status(self, bot: KingBot) -> str:
        now = datetime.now(timezone.utc)
        if bot.is_defeated and bot.cooldown_until and bot.cooldown_until > now:
            remaining = int((bot.cooldown_until - now).total_seconds())
            return f"⏳ КД: {cooldown_service.format_ttl(remaining)}"
        pct = int(bot.districts_captured / bot.districts_total * 100) if bot.districts_total > 0 else 0
        return f"{bot.districts_captured}/{bot.districts_total} районов ({pct}%)"


king_bot_service = KingBotService()