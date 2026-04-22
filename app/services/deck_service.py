import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.character import UserCharacter
from app.models.skill import UserMastery
from app.services.cooldown_service import cooldown_service
from app.services.potion_service import potion_service
from app.data.characters import CHARACTERS, RANK_CONFIG_MAP


async def _get_mastery(session: AsyncSession, user_id: int) -> UserMastery | None:
    result = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user_id)
    )
    return result.scalar_one_or_none()


class DeckService:

    async def try_get_ticket(self, session: AsyncSession, user: User) -> dict:
        """Попытка получить тикет (раз в 5 минут)."""
        cd_key = cooldown_service.ticket_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": cooldown_service.format_ttl(ttl)}

        if user.tickets >= user.max_tickets:
            return {"ok": False, "reason": f"Хранилище полно ({user.tickets}/{user.max_tickets})"}

        # Шанс тикета
        chance = await potion_service.get_effective_ticket_chance(session, user)
        chance = min(95, chance + user.prestige_ticket_bonus)
        roll = random.randint(1, 100)
        got = roll <= chance

        # КД с учётом скорости мастерства + ticket_cd_reduction
        mastery = await _get_mastery(session, user.id)
        speed_pct = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(
            mastery.speed if mastery else 0, 0
        )
        cd_seconds = cooldown_service.apply_speed_reduction(
            5 * 60, speed_pct, user.ticket_cd_reduction
        )
        await cooldown_service.set_cooldown(cd_key, cd_seconds)

        if got:
            user.tickets += 1
            await session.flush()
            return {"ok": True, "got": True, "roll": roll, "chance": chance}

        return {"ok": True, "got": False, "roll": roll, "chance": chance}

    async def pull(self, session: AsyncSession, user: User) -> dict:
        """Крутим тикет — получаем персонажа."""
        if user.tickets <= 0:
            return {"ok": False, "reason": "Нет тикетов"}

        user.tickets -= 1

        # Взвешенный выбор персонажа
        weights = [RANK_CONFIG_MAP[c["rank"]].weight for c in CHARACTERS]
        char_data = random.choices(CHARACTERS, weights=weights, k=1)[0]

        char = UserCharacter(
            user_id=user.id,
            character_id=char_data["name"],
            rank=char_data["rank"],
            power=char_data["power"],
        )
        session.add(char)
        await session.flush()

        # Пересчёт боевой мощи
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        rank_cfg = RANK_CONFIG_MAP[char_data["rank"]]
        return {
            "ok": True,
            "character": char_data,
            "rank_label": rank_cfg.label,
            "power": char_data["power"],
        }

    async def pull_all(self, session: AsyncSession, user: User) -> list[dict]:
        """Прокрутить все тикеты сразу."""
        results = []
        while user.tickets > 0:
            result = await self.pull(session, user)
            if not result["ok"]:
                break
            results.append(result)
        return results

    async def get_collection_summary(
        self, session: AsyncSession, user_id: int
    ) -> str:
        result = await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == user_id)
        )
        chars = result.scalars().all()
        if not chars:
            return "Коллекция пуста"

        from collections import Counter
        from app.data.characters import RANK_EMOJI
        counts = Counter(c.rank for c in chars)
        rank_order = [
            "absolute", "peak", "legend", "new_legend",
            "gen_zero", "strong_king", "king", "boss", "member"
        ]
        lines = []
        for rank in rank_order:
            if rank in counts:
                emoji = RANK_EMOJI.get(rank, "❓")
                cfg = RANK_CONFIG_MAP[rank]
                lines.append(f"{emoji} {cfg.label}: {counts[rank]} шт.")
        total_power = sum(c.power for c in chars)
        lines.append(f"\n💥 Суммарная мощь персонажей: {total_power:,}")
        return "\n".join(lines)


deck_service = DeckService()