from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.squad_member import SquadMember
from app.models.character import UserCharacter
from app.data.squad import RANKS_BY_ID, STAR_BONUS_PERCENT


class SquadRepo:

    async def update_user_combat_power(
        self, session: AsyncSession, user: User
    ) -> int:
        """Единственное место расчёта боевой мощи."""

        # 1. Мощь отряда
        result = await session.execute(
            select(SquadMember).where(SquadMember.user_id == user.id)
        )
        members = result.scalars().all()
        squad_power = 0
        for m in members:
            rank_cfg = RANKS_BY_ID.get(m.rank)
            if not rank_cfg:
                continue
            star_bonus = STAR_BONUS_PERCENT.get(m.stars, 0)
            squad_power += int(m.base_power * (1 + star_bonus / 100))

        # Бонус мастерства силы
        from app.models.skill import UserMastery
        mastery_r = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = mastery_r.scalar_one_or_none()
        if mastery:
            strength_bonus = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
            squad_power = int(
                squad_power * (1 + strength_bonus.get(mastery.strength, 0) / 100)
            )

        # 2. Мощь персонажей
        char_r = await session.execute(
            select(func.sum(UserCharacter.power)).where(
                UserCharacter.user_id == user.id
            )
        )
        char_power = char_r.scalar() or 0

        # 3. Бонус от учителя
        teacher_bonus = user.teacher_power_bonus or 0

        total = squad_power + char_power + teacher_bonus

        # 4. Донат-множители
        from app.repositories.title_repo import title_repo
        mult = await title_repo.get_combat_power_mult(session, user.id)
        total = int(total * mult)

        # 5. Пробуждение (+5% за уровень)
        if user.prestige_level > 0:
            prestige_mult = 1 + (user.prestige_level * 5 / 100)
            total = int(total * prestige_mult)

        # Зелье боевой мощи
        try:
            from app.services.potion_service import potion_service
            potion_bonus = await potion_service.get_power_bonus(session, user.id)
            if potion_bonus > 0:
                total = int(total * (1 + potion_bonus / 100))
        except Exception:
            pass

        # Ограничиваем разумным максимумом (BIGINT safe)
        total = min(total, 9_000_000_000_000)

        user.combat_power = total
        await session.flush()
        return total

    async def get_squad_count(
        self, session: AsyncSession, user_id: int
    ) -> int:
        result = await session.scalar(
            select(func.count(SquadMember.id)).where(
                SquadMember.user_id == user_id
            )
        )
        return result or 0

    async def get_members_by_rank(
        self, session: AsyncSession, user_id: int
    ) -> dict[str, list[SquadMember]]:
        result = await session.execute(
            select(SquadMember).where(
                SquadMember.user_id == user_id
            ).order_by(SquadMember.rank, SquadMember.stars.desc())
        )
        members = result.scalars().all()
        grouped: dict[str, list] = {}
        for m in members:
            grouped.setdefault(m.rank, []).append(m)
        return grouped


squad_repo = SquadRepo()