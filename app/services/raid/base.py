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
    RAID_ATTACK_CD_SECONDS,
    PATH_SPIN_CRAFT_COST,
)
from app.services.raid.rewards import calc_fragments, distribute_reward


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
        ttl = await cooldown_service.get_ttl(self.boss_cd_key(boss_id, user_id))
        return {"on_cd": ttl > 0, "ttl": ttl}

    async def get_attack_cd_info(self, raid_id: int, user_id: int) -> dict:
        ttl = await cooldown_service.get_ttl(self.attack_cd_key(raid_id, user_id))
        return {"on_cd": ttl > 0, "ttl": ttl}

    async def get_bosses_cd_info_batch(self, user_id: int, boss_ids: list[str]) -> dict[str, dict]:
        """Batch-fetch CD info for multiple bosses in one Redis pipeline."""
        keys = [self.boss_cd_key(bid, user_id) for bid in boss_ids]
        async with cooldown_service.redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.ttl(key)
            ttls = await pipe.execute()
        return {
            bid: {"on_cd": ttl > 0, "ttl": max(0, ttl)}
            for bid, ttl in zip(boss_ids, ttls)
        }

    async def get_user_power_for_boss(
        self, session: AsyncSession, user: User, damage_source: str, divisor: int = 2
    ) -> int:
        if damage_source == "squad":
            result = await session.scalar(
                select(func.sum(SquadMember.base_power)).where(
                    SquadMember.user_id == user.id
                )
            )
            power = result or 0
        elif damage_source == "characters":
            result = await session.scalar(
                select(func.sum(UserCharacter.power)).where(
                    UserCharacter.user_id == user.id
                )
            )
            power = result or 0
        elif damage_source == "combat_power":
            power = user.combat_power // divisor
        else:
            power = 0

        # Круговой донат «Архангел» круг 3: +N% урон в рейдах
        raid_bonus = getattr(user, "circ_raid_bonus_pct", 0)
        if power > 0 and raid_bonus > 0:
            power = int(power * (1 + raid_bonus / 100))

        # Круговой донат «Дракон» круг 6: +15% урон в рейдах (мультипликативно)
        if power > 0 and getattr(user, "circ_dragon_active", False):
            power = int(power * 1.15)

        return power

    async def start_raid(
        self, session: AsyncSession, user: User, clan_id: str, boss_id: str
    ) -> dict:
        boss = self.get_boss(clan_id, boss_id)
        if not boss:
            return {"ok": False, "reason": "Босс не найден"}

        cd_key = self.boss_cd_key(boss_id, user.id)
        boss_cd_ttl = await cooldown_service.get_ttl(cd_key)
        if boss_cd_ttl > 0:
            return {
                "ok": False,
                "reason": f"Босс восстанавливается: {cooldown_service.format_ttl(boss_cd_ttl)}",
                "cd": boss_cd_ttl,
            }

        existing = await session.execute(
            select(RaidSession).where(
                RaidSession.user_id == user.id,
                RaidSession.is_finished == False,
            )
        )
        if existing.scalar_one_or_none():
            return {"ok": False, "reason": "У вас уже есть активный рейд!"}

        divisor = boss.get("combat_power_divisor", 2)
        power = await self.get_user_power_for_boss(session, user, boss["damage_source"], divisor)
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
            damage_dealt=power,
            started_at=now,
            ends_at=ends_at,
            is_finished=False,
            attack_count=1,
        )
        session.add(raid)
        await session.flush()

        reward_type = boss.get("reward_fragments", "ui")

        # Круговой донат «Корейский дьявол» круг 3: шанс мгновенного рейда
        instant_chance = getattr(user, "circ_instant_raid_chance", 0)
        if instant_chance > 0 and random.randint(1, 100) <= instant_chance:
            from app.services.potion_service import potion_service
            drop_bonus = await potion_service.get_raid_drop_bonus(session, user.id)
            frag_bonus = getattr(user, "fragment_bonus_pct", 0)
            total_drop = drop_bonus + frag_bonus
            fragments = calc_fragments(power, boss["base_hp"], reward_type, total_drop)
            # Круговой донат «Корейский дьявол» круг 6: шанс удвоения наград
            double_chance = getattr(user, "circ_double_raid_chance", 0)
            doubled = False
            if double_chance > 0 and random.randint(1, 100) <= double_chance:
                fragments *= 2
                doubled = True
            raid.is_finished = True
            raid.fragments_earned = fragments
            total_fragments = distribute_reward(user, reward_type, fragments)
            user.raid_boss_wins = (user.raid_boss_wins or 0) + 1
            cd_key = self.boss_cd_key(boss_id, user.id)
            speed_pct = await self._get_speed_pct(session, user)
            boss_cd = cooldown_service.apply_speed_reduction(boss["cd_hours"] * 3600, speed_pct)
            await cooldown_service.set_cooldown(cd_key, boss_cd)
            await session.flush()
            return {
                "ok": True,
                "instant": True,
                "raid_id": raid.id,
                "boss_name": boss["name"],
                "damage": power,
                "total_damage": power,
                "ends_at": ends_at,
                "fragments": fragments,
                "total_fragments": total_fragments,
                "reward_type": reward_type,
                "doubled": doubled,
            }

        attack_cd_key = self.attack_cd_key(raid.id, user.id)
        speed_pct = await self._get_speed_pct(session, user)
        attack_cd = cooldown_service.apply_speed_reduction(RAID_ATTACK_CD_SECONDS, speed_pct)
        await cooldown_service.set_cooldown(attack_cd_key, attack_cd)

        return {
            "ok": True,
            "instant": False,
            "raid_id": raid.id,
            "boss_name": boss["name"],
            "damage": power,
            "total_damage": power,
            "ends_at": ends_at,
            "duration_hours": boss["raid_duration_seconds"] // 3600,
            "reward_type": reward_type,
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
        attack_ttl = await cooldown_service.get_ttl(attack_cd_key)
        if attack_ttl > 0:
            return {
                "ok": False,
                "reason": f"Следующая атака через: {cooldown_service.format_ttl(attack_ttl)}",
                "cd": attack_ttl,
            }

        boss = self.get_boss(raid.clan_id, raid.boss_id)
        if not boss:
            return {"ok": False, "reason": "Босс не найден"}

        divisor = boss.get("combat_power_divisor", 2)
        power = await self.get_user_power_for_boss(session, user, boss["damage_source"], divisor)
        if power == 0:
            return {"ok": False, "reason": "Нет бойцов для атаки!"}

        raid.damage_dealt += power
        raid.attack_count += 1

        speed_pct = await self._get_speed_pct(session, user)
        attack_cd = cooldown_service.apply_speed_reduction(RAID_ATTACK_CD_SECONDS, speed_pct)
        await cooldown_service.set_cooldown(attack_cd_key, attack_cd)

        boss_killed = raid.damage_dealt >= boss["base_hp"]
        if boss_killed:
            reward_type = boss.get("reward_fragments", "ui")
            from app.services.potion_service import potion_service
            drop_bonus = await potion_service.get_raid_drop_bonus(session, user.id)
            # Круговой донат «Повелитель подземелья»: бонус к фрагментам
            frag_bonus = getattr(user, "fragment_bonus_pct", 0)
            total_drop = drop_bonus + frag_bonus
            fragments = calc_fragments(raid.damage_dealt, boss["base_hp"], reward_type, total_drop)
            # Круговой донат «Корейский дьявол» круг 6: шанс удвоения наград
            doubled = False
            double_chance = getattr(user, "circ_double_raid_chance", 0)
            if double_chance > 0 and random.randint(1, 100) <= double_chance:
                fragments *= 2
                doubled = True
            raid.is_finished = True
            raid.fragments_earned = fragments
            total_fragments = distribute_reward(user, reward_type, fragments)
            user.raid_boss_wins = (user.raid_boss_wins or 0) + 1

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
                "boss_id": raid.boss_id,
                "remaining": 0,
                "doubled": doubled,
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
        from app.services.potion_service import potion_service
        drop_bonus = await potion_service.get_raid_drop_bonus(session, user.id)
        # Круговой донат «Повелитель подземелья»: бонус к фрагментам
        frag_bonus = getattr(user, "fragment_bonus_pct", 0)
        total_drop = drop_bonus + frag_bonus
        fragments = calc_fragments(raid.damage_dealt, boss["base_hp"], reward_type, total_drop)
        # Круговой донат «Корейский дьявол» круг 6: шанс удвоения наград
        doubled = False
        double_chance = getattr(user, "circ_double_raid_chance", 0)
        if double_chance > 0 and random.randint(1, 100) <= double_chance:
            fragments *= 2
            doubled = True
        raid.is_finished = True
        raid.fragments_earned = fragments
        total_fragments = distribute_reward(user, reward_type, fragments)
        user.raid_boss_wins = (user.raid_boss_wins or 0) + 1

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
            "boss_id": raid.boss_id,
            "doubled": doubled,
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

    async def _get_max_extra_attacks(self, session: AsyncSession, user: User) -> int:
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

    # kept for backward compat — delegates to module-level function
    def _calc_fragments(self, damage: int, boss_hp: int, reward_type: str = "ui", drop_bonus_pct: int = 0) -> int:
        return calc_fragments(damage, boss_hp, reward_type, drop_bonus_pct)

    async def craft_path_spin(
        self, session: AsyncSession, user: User
    ) -> dict:
        if not user.skill_path:
            return {"ok": False, "reason": "Сначала выбери путь в Навыках!"}
        if user.path_fragments < PATH_SPIN_CRAFT_COST:
            return {
                "ok": False,
                "reason": (
                    f"Недостаточно фрагментов Пути "
                    f"(нужно {PATH_SPIN_CRAFT_COST}, есть {user.path_fragments})"
                ),
            }
        user.path_fragments -= PATH_SPIN_CRAFT_COST
        from app.services.skill_service import skill_service
        result = await skill_service.spin_for_random_extra_skill(session, user)
        await session.flush()
        return result

    async def craft_ui(
        self, session: AsyncSession, user: User, target_level: int
    ) -> dict:
        if user.ui_is_donat:
            return {"ok": False, "reason": "У вас донатный УИ — уже максимальный!"}

        if target_level < 1 or target_level > 4:
            return {"ok": False, "reason": "Неверный уровень"}

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

        return {
            "ok": True,
            "new_level": target_level,
            "cost": cost,
            "fragments_left": user.ui_fragments,
        }

    async def craft_mg_level(
        self, session: AsyncSession, user: User, potion_type: str, target_level: int
    ) -> dict:
        """Открыть уровень зелья (Гений медицины) за фрагменты алхимии."""
        from app.handlers.skills.med_genius import MG_POTION_MAP, MG_BUY_MAX_LEVEL, MG_LEVEL_COSTS

        if getattr(user, "med_genius_donat", False):
            return {"ok": False, "reason": "Донат активен — все уровни максимальны!"}

        cfg = MG_POTION_MAP.get(potion_type)
        if not cfg:
            return {"ok": False, "reason": "Неизвестный тип зелья"}

        current = getattr(user, cfg["level_field"], 0)
        if target_level != current + 1:
            return {"ok": False, "reason": "Открывайте уровни по порядку"}
        if target_level > MG_BUY_MAX_LEVEL:
            return {"ok": False, "reason": "Уровень 6 — только через донат"}

        cost  = MG_LEVEL_COSTS[current]  # индекс = текущий уровень (0 = стоимость ур.1)
        frags = getattr(user, "alchemy_fragments", 0)
        if frags < cost:
            return {
                "ok": False,
                "reason": f"Недостаточно 🧪 фрагментов алхимии: {frags}/{cost}",
            }

        user.alchemy_fragments -= cost
        setattr(user, cfg["level_field"], target_level)
        await session.flush()

        from app.data.shop import MG_TIERS
        tier = MG_TIERS[potion_type][target_level - 1]
        return {
            "ok": True,
            "new_level": target_level,
            "effect": tier.effect_value,
            "cost": cost,
            "fragments_left": user.alchemy_fragments,
        }

    async def _get_speed_pct(self, session: AsyncSession, user: User) -> int:
        from sqlalchemy import select as sa_select
        from app.models.skill import UserMastery
        speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        speed = await session.scalar(
            sa_select(UserMastery.speed).where(UserMastery.user_id == user.id)
        )
        raw = speed_levels.get(speed or 0, 0)
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
