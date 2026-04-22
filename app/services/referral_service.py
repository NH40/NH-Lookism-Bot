from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.referral import Referral


class ReferralService:

    async def register_with_referral(
        self,
        session: AsyncSession,
        student: User,
        teacher_tg_id: int,
    ) -> bool:
        """Привязывает ученика к учителю при регистрации."""
        result = await session.execute(
            select(User).where(User.tg_id == teacher_tg_id)
        )
        teacher = result.scalar_one_or_none()
        if not teacher or teacher.id == student.id:
            return False

        student.referred_by = teacher.id
        # Фиксируем бонус мощи от учителя (5% от мощи учителя)
        student.teacher_power_bonus = int(teacher.combat_power * 0.05)

        referral = Referral(
            teacher_id=teacher.id,
            student_id=student.id,
        )
        session.add(referral)
        await session.flush()
        return True

    async def get_students(
        self, session: AsyncSession, teacher_id: int
    ) -> list[User]:
        result = await session.execute(
            select(User).where(User.referred_by == teacher_id)
        )
        return result.scalars().all()

    async def get_teacher(
        self, session: AsyncSession, user: User
    ) -> User | None:
        if not user.referred_by:
            return None
        result = await session.execute(
            select(User).where(User.id == user.referred_by)
        )
        return result.scalar_one_or_none()


referral_service = ReferralService()