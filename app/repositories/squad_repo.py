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
        """
        ЕДИНСТВЕННОЕ место расчёта боевой мощи.
        squad_power + char_power + teacher_bonus,
        с учётом донат-множителей.
        """
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
        mastery_result = await session.execute(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        mastery = mastery_result.scalar_one_or_none()
        if mastery:
            strength_bonus = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
            squad_power = int(
                squad_power * (1 + strength_bonus.get(mastery.strength, 0) / 100)
            )

        # 2. Мощь персонажей
        char_result = await session.execute(
            select(func.sum(UserCharacter.power)).where(
                UserCharacter.user_id == user.id
            )
        )
        char_power = char_result.scalar() or 0

        # 3. Бонус от учителя
        teacher_bonus = user.teacher_power_bonus

        total = squad_power + char_power + teacher_bonus

        # 4. Донат-множители combat_power_mult
        from app.repositories.title_repo import title_repo
        mult = await title_repo.get_combat_power_mult(session, user.id)
        total = int(total * mult)

        # 5. Пробуждение (prestige даёт +5% за уровень к базе отряда)
        if user.prestige_level > 0:
            prestige_mult = 1 + (user.prestige_level * 5 / 100)
            total = int(total * prestige_mult)

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