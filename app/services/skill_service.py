from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.skill import UserMastery, UserPathSkills
from app.data.skills import MASTERY_BY_ID, PATH_SKILLS


class SkillService:

    async def get_or_create_mastery(
        self, session: AsyncSession, user_id: int
    ) -> UserMastery:
        result = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user_id)
        )
        mastery = result.scalar_one_or_none()
        if not mastery:
            mastery = UserMastery(user_id=user_id)
            session.add(mastery)
            await session.flush()
        return mastery

    async def upgrade_mastery(
        self, session: AsyncSession, user: User, skill_id: str
    ) -> dict:
        cfg = MASTERY_BY_ID.get(skill_id)
        if not cfg:
            return {"ok": False, "reason": "Навык не найден"}

        mastery = await self.get_or_create_mastery(session, user.id)
        current_level = getattr(mastery, skill_id, 0)
        next_level = current_level + 1

        if next_level >= len(cfg.levels):
            return {"ok": False, "reason": "Максимальный уровень"}

        level_cfg = cfg.levels[next_level]
        if user.nh_coins < level_cfg.cost:
            return {"ok": False, "reason": f"Нужно {level_cfg.cost:,} NHCoin"}

        user.nh_coins -= level_cfg.cost
        user.coins_spent += level_cfg.cost
        setattr(mastery, skill_id, next_level)

        # Применяем бонус к User
        await self._apply_mastery_bonus(session, user, skill_id, next_level)
        await session.flush()

        return {
            "ok": True,
            "skill": skill_id,
            "new_level": next_level,
            "bonus": level_cfg.bonus,
        }

    async def _apply_mastery_bonus(
        self, session: AsyncSession, user: User, skill_id: str, level: int
    ) -> None:
        cfg = MASTERY_BY_ID[skill_id]
        bonus = cfg.levels[level].bonus
        prev_bonus = cfg.levels[level - 1].bonus if level > 0 else 0
        delta = bonus - prev_bonus

        if skill_id == "technique":
            # Техника влияет на тренировку И доход
            user.train_bonus_percent += delta
            user.income_bonus_percent += delta
            from app.services.business_service import business_service
            await business_service._recalc_income(session, user)
        elif skill_id == "strength":
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, user)

    async def choose_path(
        self, session: AsyncSession, user: User, path: str
    ) -> dict:
        if user.skill_path:
            return {"ok": False, "reason": f"Путь уже выбран: {user.skill_path}"}
        if path not in PATH_SKILLS:
            return {"ok": False, "reason": "Неизвестный путь"}
        user.skill_path = path
        await session.flush()
        return {"ok": True, "path": path}

    async def buy_path_skill(
        self, session: AsyncSession, user: User, skill_id: str
    ) -> dict:
        if not user.skill_path:
            return {"ok": False, "reason": "Сначала выберите путь"}

        skills = PATH_SKILLS.get(user.skill_path, [])
        skill = next((s for s in skills if s.skill_id == skill_id), None)
        if not skill:
            return {"ok": False, "reason": "Навык не найден в вашем пути"}

        # Проверяем — не куплен ли уже
        result = await session.execute(
            select(UserPathSkills).where(
                UserPathSkills.user_id == user.id,
                UserPathSkills.skill_id == skill_id,
            )
        )
        if result.scalar_one_or_none():
            return {"ok": False, "reason": "Навык уже куплен"}

        if user.skill_path_points < skill.cost:
            return {
                "ok": False,
                "reason": f"Нужно {skill.cost} очков пути (у вас {user.skill_path_points})",
            }

        user.skill_path_points -= skill.cost

        record = UserPathSkills(user_id=user.id, skill_id=skill_id)
        session.add(record)
        await session.flush()

        # Применяем эффект
        await self._apply_path_skill(session, user, skill)
        return {"ok": True, "skill": skill.name}

    async def _apply_path_skill(self, session, user: User, skill) -> None:
        multiplier = user.skill_path_bonus_multiplier
        for field, value in skill.effect.items():
            if isinstance(value, bool):
                setattr(user, field, value)
            elif isinstance(value, float):
                current = getattr(user, field, 1.0)
                setattr(user, field, current * value)
            else:
                current = getattr(user, field, 0)
                bonus = int(value * multiplier)
                setattr(user, field, current + bonus)

        # double_attack — проверяем комбо
        if user.double_attack:
            self._update_extra_attack(user)

        # Пересчёты
        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        await session.flush()

    def _update_extra_attack(self, user: User) -> None:
        """extra_attack_count: 1 = 2 атаки, 2 = 3 атаки."""
        # Считаем сколько источников double_attack
        sources = 0
        # Проверяется снаружи через title_service при выдаче доната
        # Здесь просто устанавливаем минимум 1
        if user.extra_attack_count < 1:
            user.extra_attack_count = 1

    async def get_path_skills_bought(
        self, session: AsyncSession, user_id: int
    ) -> list[str]:
        result = await session.execute(
            select(UserPathSkills.skill_id).where(
                UserPathSkills.user_id == user_id
            )
        )
        return result.scalars().all()


skill_service = SkillService()