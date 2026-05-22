"""Тикеты и прокрутка гачи."""
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.character import UserCharacter
from app.models.skill import UserMastery
from app.services.cooldown_service import cooldown_service
from app.services.potion_service import potion_service
from app.data.characters import CHARACTERS, RANK_CONFIG_MAP
from app.constants.cards import LEVEL_MULTIPLIERS


def _effective_power(base_power: int, level: int) -> int:
    return int(base_power * LEVEL_MULTIPLIERS.get(level, 1.0))


async def _get_mastery(session: AsyncSession, user_id: int) -> UserMastery | None:
    return await session.scalar(
        select(UserMastery).where(UserMastery.user_id == user_id)
    )


class GachaService:
    """Тикеты, прокрутка, формирование записей UserCharacter."""

    def __init__(self) -> None:
        # Pre-compute weights once — reused across all pull calls (avoid per-pull recalculation)
        self._weights: list[float] = [RANK_CONFIG_MAP[c["rank"]].weight for c in CHARACTERS]

    async def try_get_ticket(self, session: AsyncSession, user: User) -> dict:
        """Попытка получить тикет раз в 5 минут."""
        cd_key = cooldown_service.ticket_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": cooldown_service.format_ttl(ttl)}

        if user.tickets >= user.max_tickets:
            return {"ok": False, "reason": f"Хранилище полно ({user.tickets}/{user.max_tickets})"}

        cap = getattr(user, "max_ticket_chance", 70)
        chance = await potion_service.get_effective_ticket_chance(session, user)
        chance = min(
            cap,
            chance + user.prestige_ticket_bonus
            + getattr(user, "clan_ticket_bonus", 0)
            + getattr(user, "clan_donat_ticket_bonus", 0),
        )
        roll = random.randint(1, 100)
        got = roll <= chance

        mastery = await _get_mastery(session, user.id)
        raw_speed = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}.get(
            mastery.speed if mastery else 0, 0
        )
        speed_pct = int(raw_speed * getattr(user, "skill_path_bonus_multiplier", 1.0))
        cd_seconds = max(60, cooldown_service.apply_speed_reduction(
            5 * 60, speed_pct, getattr(user, "ticket_cd_reduction", 0)
        ))
        await cooldown_service.set_cooldown(cd_key, cd_seconds)

        if got:
            double = getattr(user, "double_ticket", False)
            gained = 2 if double and (user.tickets + 1 < user.max_tickets) else 1
            user.tickets = min(user.max_tickets, user.tickets + gained)
            await session.flush()
            return {"ok": True, "got": True, "roll": roll, "chance": chance,
                    "double": double and gained == 2}

        return {"ok": True, "got": False, "roll": roll, "chance": chance, "double": False}

    def _pick_char(self, user: User) -> dict:
        user.tickets -= 1
        return random.choices(CHARACTERS, weights=self._weights, k=1)[0]

    def _make_uc(self, user_id: int, char_data: dict) -> UserCharacter:
        bp = char_data["power"]
        return UserCharacter(
            user_id=user_id,
            character_id=char_data["name"],
            rank=char_data["rank"],
            base_power=bp,
            power=bp,
            level=0,
        )

    async def _refresh_power(self, session: AsyncSession, user: User) -> None:
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

    async def pull(self, session: AsyncSession, user: User) -> dict:
        if user.tickets <= 0:
            return {"ok": False, "reason": "Нет тикетов"}
        char_data = self._pick_char(user)
        session.add(self._make_uc(user.id, char_data))
        await session.flush()
        await self._refresh_power(session, user)
        return {
            "ok": True,
            "character": char_data,
            "rank_label": RANK_CONFIG_MAP[char_data["rank"]].label,
            "power": char_data["power"],
        }

    async def pull_n(self, session: AsyncSession, user: User, n: int) -> list[dict]:
        results = []
        for _ in range(n):
            if user.tickets <= 0:
                break
            char_data = self._pick_char(user)
            session.add(self._make_uc(user.id, char_data))
            results.append({
                "ok": True,
                "character": char_data,
                "rank_label": RANK_CONFIG_MAP[char_data["rank"]].label,
                "power": char_data["power"],
            })
        if results:
            await session.flush()
            await self._refresh_power(session, user)
        return results

    async def pull_all(self, session: AsyncSession, user: User) -> list[dict]:
        results = []
        while user.tickets > 0:
            char_data = self._pick_char(user)
            session.add(self._make_uc(user.id, char_data))
            results.append({
                "ok": True,
                "character": char_data,
                "rank_label": RANK_CONFIG_MAP[char_data["rank"]].label,
                "power": char_data["power"],
            })
        if results:
            await session.flush()
            await self._refresh_power(session, user)
        return results


gacha_service = GachaService()
