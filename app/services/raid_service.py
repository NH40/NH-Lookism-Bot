import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.raid import RaidSession
from app.models.squad_member import SquadMember
from app.models.character import UserCharacter
from app.services.cooldown_service import cooldown_service
from app.constants.raid import (
    RAID_BOSSES, UI_CRAFT_COST, UI_LEVEL_PERKS,
    RAID_ATTACK_CD_SECONDS, RAID_ATTACK_CD_KEY,
    ALCHEMY_CRAFT_COST, ALCHEMY_MAX_FRAGMENTS_PER_RAID,
)


class RaidService:

    def boss_cd_key(self, boss_id: str, user_id: int) -> str:
        return f"raid:{boss_id}:{user_id}"

    def attack_cd_key(self, raid_id: int, user_id: int) -> str:
        return f"raid_attack:{raid_id}:{user_id}"

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

    async def get_attack_cd_info(self, raid_id: int, user_id: int) -> dict:
        cd_key = self.attack_cd_key(raid_id, user_id)
        on_cd = await cooldown_service.is_on_cooldown(cd_key)
        ttl = await cooldown_service.get_ttl(cd_key) if on_cd else 0
        return {"on_cd": on_cd, "ttl": ttl}

    async def get_user_power_for_boss(
        self, session: AsyncSession, user: User, damage_source: str
    ) -> int:
        if damage_source == "squad":
            result = await session.scalar(
                select(func.sum(SquadMember.base_power)).where(
                    SquadMember.user_id == user.id
                )
            )
            return result or 0
        elif damage_source == "characters":
            result = await session.scalar(
                select(func.sum(UserCharacter.power)).where(
                    UserCharacter.user_id == user.id
                )
            )
            return result or 0
        elif damage_source == "combat_power":
            return user.combat_power // 2
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

        existing = await session.execute(
            select(RaidSession).where(
                RaidSession.user_id == user.id,
                RaidSession.is_finished == False,
            )
        )
        if existing.scalar_one_or_none():
            return {"ok": False, "reason": "У вас уже есть активный рейд!"}

        power = await self.get_user_power_for_boss(session, user, boss["damage_source"])
        if power == 0:
            if boss["damage_source"] == "squad":
                source_name = "статистов"
            elif boss["damage_source"] == "combat_power":
                source_name = "боевой мощи"
            else:
                source_name = "персонажей"
            return {"ok": False, "reason": f"Нет {source_name} для атаки!"}

        now = datetime.now(timezone.utc)
        ends_at = now + timedelta(seconds=boss["raid_duration_seconds"])

        raid = RaidSession(
            user_id=user.id,
            boss_id=boss_id,
            clan_id=clan_id,
            damage_dealt=power,  # первая атака
            started_at=now,
            ends_at=ends_at,
            is_finished=False,
            attack_count=1,
        )
        session.add(raid)
        await session.flush()

        # Ставим КД на первую атаку
        speed_pct = await self._get_speed_pct(session, user)
        attack_cd = cooldown_service.apply_speed_reduction(RAID_ATTACK_CD_SECONDS, speed_pct)
        attack_cd_key = self.attack_cd_key(raid.id, user.id)
        await cooldown_service.set_cooldown(attack_cd_key, attack_cd)

        return {
            "ok": True,
            "raid_id": raid.id,
            "boss_name": boss["name"],
            "damage": power,
            "total_damage": power,
            "ends_at": ends_at,
            "duration_hours": boss["raid_duration_seconds"] // 3600,  
        }

    async def attack_boss(
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
            return {"ok": False, "reason": "Активный рейд не найден"}

        now = datetime.now(timezone.utc)
        if now >= raid.ends_at:
            return {"ok": False, "reason": "Время рейда истекло! Забери награду."}

        attack_cd_key = self.attack_cd_key(raid_id, user.id)
        if await cooldown_service.is_on_cooldown(attack_cd_key):
            ttl = await cooldown_service.get_ttl(attack_cd_key)
            return {
                "ok": False,
                "reason": f"Следующая атака через: {cooldown_service.format_ttl(ttl)}",
                "cd": ttl,
            }

        boss = self.get_boss(raid.clan_id, raid.boss_id)
        if not boss:
            return {"ok": False, "reason": "Босс не найден"}

        power = await self.get_user_power_for_boss(session, user, boss["damage_source"])
        if power == 0:
            return {"ok": False, "reason": "Нет бойцов для атаки!"}

        raid.damage_dealt += power
        raid.attack_count += 1

        speed_pct = await self._get_speed_pct(session, user)
        attack_cd = cooldown_service.apply_speed_reduction(RAID_ATTACK_CD_SECONDS, speed_pct)
        await cooldown_service.set_cooldown(attack_cd_key, attack_cd)

        # ── Проверяем убит ли босс ──────────────────────────────────────
        boss_killed = raid.damage_dealt >= boss["base_hp"]
        if boss_killed:
            reward_type = boss.get("reward_fragments", "ui")
            fragments = self._calc_fragments(raid.damage_dealt, boss["base_hp"], reward_type)
            raid.is_finished = True
            raid.fragments_earned = fragments
            if reward_type == "alchemy":
                user.alchemy_fragments += fragments
                total_fragments = user.alchemy_fragments
            else:
                user.ui_fragments += fragments
                total_fragments = user.ui_fragments

            cd_key = self.boss_cd_key(raid.boss_id, user.id)
            await cooldown_service.set_cooldown(cd_key, boss["cd_hours"] * 3600)

            await session.flush()
            return {
                "ok": True,
                "boss_killed": True,
                "damage": power,
                "total_damage": raid.damage_dealt,
                "attack_count": raid.attack_count,
                "fragments": fragments,
                "total_fragments": total_fragments,
                "reward_type": reward_type,
                "boss_name": boss["name"],
                "remaining": 0,
            }

        await session.flush()

        remaining = max(0, int((raid.ends_at - now).total_seconds()))
        return {
            "ok": True,
            "boss_killed": False,
            "damage": power,
            "total_damage": raid.damage_dealt,
            "attack_count": raid.attack_count,
            "remaining": remaining,
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

        if now < raid.ends_at:
            remaining = int((raid.ends_at - now).total_seconds())
            return {
                "ok": False,
                "reason": f"Рейд ещё идёт: {cooldown_service.format_ttl(remaining)}",
                "remaining": remaining,
            }

        reward_type = boss.get("reward_fragments", "ui")
        fragments = self._calc_fragments(raid.damage_dealt, boss["base_hp"], reward_type)
        raid.is_finished = True
        raid.fragments_earned = fragments
        if reward_type == "alchemy":
            user.alchemy_fragments += fragments
            total_fragments = user.alchemy_fragments
        else:
            user.ui_fragments += fragments
            total_fragments = user.ui_fragments

        # КД на босса с учётом скорости
        speed_pct = await self._get_speed_pct(session, user)
        boss_cd = cooldown_service.apply_speed_reduction(boss["cd_hours"] * 3600, speed_pct)
        cd_key = self.boss_cd_key(raid.boss_id, user.id)
        await cooldown_service.set_cooldown(cd_key, boss_cd)

        await session.flush()

        return {
            "ok": True,
            "fragments": fragments,
            "total_fragments": total_fragments,
            "reward_type": reward_type,
            "damage": raid.damage_dealt,
            "attack_count": raid.attack_count,
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

    def _calc_fragments(self, damage: int, boss_hp: int, reward_type: str = "ui") -> int:
        ratio = min(1.0, damage / boss_hp)
        if reward_type == "alchemy":
            if ratio >= 0.5:
                return random.randint(20, ALCHEMY_MAX_FRAGMENTS_PER_RAID)
            elif ratio >= 0.2:
                return random.randint(12, 19)
            elif ratio >= 0.05:
                return random.randint(5, 11)
            else:
                return random.randint(1, 4)
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
        if user.ui_is_donat:
            return {"ok": False, "reason": "У вас донатный УИ — уже максимальный!"}

        if target_level < 1 or target_level > 4:
            return {"ok": False, "reason": "Неверный уровень"}

        # Нельзя пропускать уровни
        if target_level != user.ui_level + 1:
            needed = user.ui_level + 1
            return {
                "ok": False,
                "reason": f"Сначала получи УИ {needed} уровня!",
            }

        cost = UI_CRAFT_COST[target_level]

        if user.ui_fragments < cost:
            return {
                "ok": False,
                "reason": f"Недостаточно фрагментов (нужно {cost}, есть {user.ui_fragments})",
            }

        user.ui_fragments -= cost
        user.ui_level = target_level
        self._apply_ui_level(user, target_level)
        await session.flush()

        if user.donat_ui_potion and user.ui_auto_potion:
            from app.services.potion_service import potion_service
            await potion_service.buy_missing(session, user)

        return {
            "ok": True,
            "new_level": target_level,
            "cost": cost,
            "fragments_left": user.ui_fragments,
        }

    async def craft_alchemy_ui(
        self, session: AsyncSession, user: User
    ) -> dict:
        if user.donat_ui_potion:
            return {"ok": False, "reason": "УИ Алхимии уже получен!"}
        if user.alchemy_fragments < ALCHEMY_CRAFT_COST:
            return {
                "ok": False,
                "reason": (
                    f"Недостаточно фрагментов алхимии "
                    f"(нужно {ALCHEMY_CRAFT_COST}, есть {user.alchemy_fragments})"
                ),
            }
        user.alchemy_fragments -= ALCHEMY_CRAFT_COST
        user.donat_ui_potion = True
        user.ui_auto_potion = True
        from app.services.potion_service import potion_service
        await potion_service.buy_missing(session, user)
        await session.flush()
        return {"ok": True, "fragments_left": user.alchemy_fragments}

    async def _get_speed_pct(self, session: AsyncSession, user: User) -> int:
        """Получает % сокращения КД от мастерства скорости с учётом мультипликатора."""
        from sqlalchemy import select
        from app.models.skill import UserMastery
        speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        r = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = r.scalar_one_or_none()
        raw = speed_levels.get(mastery.speed if mastery else 0, 0)
        return int(raw * user.skill_path_bonus_multiplier)
    
    def _apply_ui_level(self, user: User, level: int) -> None:
        user.ultra_instinct = level >= 1
        user.ui_auto_recruit = level >= 1
        user.ui_auto_train   = level >= 2
        user.ui_auto_ticket  = level >= 3
        user.ui_auto_pull    = level >= 4

    def apply_donat_ui(self, user: User) -> None:
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
        if not user.ui_is_donat:
            user.ui_level = 0
            user.ultra_instinct = False
            user.true_ultra_instinct = False
            user.ui_auto_recruit = False
            user.ui_auto_train = False
            user.ui_auto_ticket = False
            user.ui_auto_pull = False
            user.ui_fragments = 0


raid_service = RaidService()