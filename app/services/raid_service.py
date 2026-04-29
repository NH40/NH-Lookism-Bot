import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.raid import RaidSession
from app.models.squad_member import SquadMember
from app.models.character import UserCharacter
from app.services.cooldown_service import cooldown_service
from app.constants.raid import RAID_BOSSES, UI_CRAFT_COST, UI_LEVEL_PERKS


class RaidService:

    def boss_cd_key(self, boss_id: str, user_id: int) -> str:
        return f"raid:{boss_id}:{user_id}"

    def get_clan(self, clan_id: str) -> dict | None:
        return RAID_BOSSES.get(clan_id)

    def get_boss(self, clan_id: str, boss_id: str) -> dict | None:
        clan = self.get_clan(clan_id)
        if not clan:
            return None
        return clan["bosses"].get(boss_id)

    async def get_boss_cd_info(self, user_id: int, boss_id: str) -> dict:
        cd_key = self.boss_cd_key(boss_id, user_id)
        on_cd = await cooldown_service.is_on_cooldown(cd_key)
        ttl = await cooldown_service.get_ttl(cd_key) if on_cd else 0
        return {"on_cd": on_cd, "ttl": ttl}

    async def get_user_power_for_boss(
        self, session: AsyncSession, user: User, damage_source: str
    ) -> int:
        """Считает урон в зависимости от источника босса."""
        if damage_source == "squad":
            # Урон = суммарная мощь статистов
            result = await session.scalar(
                select(func.sum(SquadMember.base_power)).where(
                    SquadMember.user_id == user.id
                )
            )
            return result or 0

        elif damage_source == "characters":
            # Урон = суммарная мощь уникальных персонажей
            result = await session.scalar(
                select(func.sum(UserCharacter.power)).where(
                    UserCharacter.user_id == user.id
                )
            )
            return result or 0

        return 0

    async def start_raid(
        self, session: AsyncSession, user: User, clan_id: str, boss_id: str
    ) -> dict:
        boss = self.get_boss(clan_id, boss_id)
        if not boss:
            return {"ok": False, "reason": "Босс не найден"}

        cd_key = self.boss_cd_key(boss_id, user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {
                "ok": False,
                "reason": f"Босс восстанавливается: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        # Проверяем нет ли активного рейда
        existing = await session.execute(
            select(RaidSession).where(
                RaidSession.user_id == user.id,
                RaidSession.is_finished == False,
            )
        )
        if existing.scalar_one_or_none():
            return {"ok": False, "reason": "У вас уже есть активный рейд!"}

        # Считаем урон
        power = await self.get_user_power_for_boss(session, user, boss["damage_source"])
        if power == 0:
            source_name = "статистов" if boss["damage_source"] == "squad" else "персонажей"
            return {"ok": False, "reason": f"Нет {source_name} для атаки!"}

        now = datetime.now(timezone.utc)
        ends_at = now + timedelta(seconds=boss["raid_duration_seconds"])

        raid = RaidSession(
            user_id=user.id,
            boss_id=boss_id,
            clan_id=clan_id,
            damage_dealt=power,
            started_at=now,
            ends_at=ends_at,
            is_finished=False,
        )
        session.add(raid)
        await session.flush()

        return {
            "ok": True,
            "raid_id": raid.id,
            "boss_name": boss["name"],
            "damage": power,
            "ends_at": ends_at,
            "duration_hours": boss["raid_duration_seconds"] // 3600,
        }

    async def finish_raid(
        self, session: AsyncSession, user: User, raid_id: int
    ) -> dict:
        result = await session.execute(
            select(RaidSession).where(
                RaidSession.id == raid_id,
                RaidSession.user_id == user.id,
                RaidSession.is_finished == False,
            )
        )
        raid = result.scalar_one_or_none()
        if not raid:
            return {"ok": False, "reason": "Рейд не найден"}

        now = datetime.now(timezone.utc)
        boss = self.get_boss(raid.clan_id, raid.boss_id)
        if not boss:
            return {"ok": False, "reason": "Босс не найден"}

        # Проверяем завершился ли рейд
        if now < raid.ends_at:
            remaining = int((raid.ends_at - now).total_seconds())
            return {
                "ok": False,
                "reason": f"Рейд ещё идёт: {cooldown_service.format_ttl(remaining)}",
                "remaining": remaining,
            }

        # Считаем фрагменты в зависимости от урона
        fragments = self._calc_fragments(raid.damage_dealt, boss["base_hp"])
        raid.is_finished = True
        raid.fragments_earned = fragments

        # Начисляем фрагменты
        user.ui_fragments += fragments

        # Ставим КД на босса
        cd_key = self.boss_cd_key(raid.boss_id, user.id)
        await cooldown_service.set_cooldown(cd_key, boss["cd_hours"] * 3600)

        await session.flush()

        return {
            "ok": True,
            "fragments": fragments,
            "total_fragments": user.ui_fragments,
            "damage": raid.damage_dealt,
            "boss_name": boss["name"],
        }

    async def get_active_raid(
        self, session: AsyncSession, user_id: int
    ) -> RaidSession | None:
        result = await session.execute(
            select(RaidSession).where(
                RaidSession.user_id == user_id,
                RaidSession.is_finished == False,
            )
        )
        return result.scalar_one_or_none()

    def _calc_fragments(self, damage: int, boss_hp: int) -> int:
        """Чем больше урон относительно HP босса — тем больше фрагментов."""
        ratio = min(1.0, damage / boss_hp)
        if ratio >= 0.5:
            return random.randint(15, 25)
        elif ratio >= 0.2:
            return random.randint(8, 15)
        elif ratio >= 0.05:
            return random.randint(3, 8)
        else:
            return random.randint(1, 3)

    async def craft_ui(
        self, session: AsyncSession, user: User, target_level: int
    ) -> dict:
        """Крафт УИ за фрагменты."""
        if user.ui_is_donat:
            return {"ok": False, "reason": "У вас донатный УИ — уже максимальный!"}

        if target_level < 1 or target_level > 4:
            return {"ok": False, "reason": "Неверный уровень"}

        if user.ui_level >= target_level:
            return {"ok": False, "reason": f"УИ уровня {target_level} уже получен"}

        # Суммарная стоимость до target_level
        total_cost = sum(UI_CRAFT_COST[lvl] for lvl in range(user.ui_level + 1, target_level + 1))

        if user.ui_fragments < total_cost:
            return {
                "ok": False,
                "reason": f"Недостаточно фрагментов (нужно {total_cost}, есть {user.ui_fragments})",
            }

        user.ui_fragments -= total_cost
        user.ui_level = target_level
        self._apply_ui_level(user, target_level)
        await session.flush()

        return {
            "ok": True,
            "new_level": target_level,
            "cost": total_cost,
            "fragments_left": user.ui_fragments,
        }

    def _apply_ui_level(self, user: User, level: int) -> None:
        """Применяет бонусы УИ по уровню."""
        user.ultra_instinct = level >= 1
        user.ui_auto_recruit = level >= 1
        user.ui_auto_train   = level >= 2
        user.ui_auto_ticket  = level >= 3
        user.ui_auto_pull    = level >= 4

    def apply_donat_ui(self, user: User) -> None:
        """Выдаёт донатный УИ 4 уровня перманентно."""
        user.ui_is_donat = True
        user.ui_level = 4
        user.ultra_instinct = True
        user.true_ultra_instinct = True
        user.ui_auto_recruit = True
        user.ui_auto_train = True
        user.ui_auto_ticket = True
        user.ui_auto_pull = True
        user.max_tickets = 999999

    def reset_game_ui(self, user: User) -> None:
        """Сбрасывает игровой УИ при патче (донатный не трогает)."""
        if not user.ui_is_donat:
            user.ui_level = 0
            user.ultra_instinct = False
            user.ui_auto_recruit = False
            user.ui_auto_train = False
            user.ui_auto_ticket = False
            user.ui_auto_pull = False
            user.ui_fragments = 0


raid_service = RaidService()