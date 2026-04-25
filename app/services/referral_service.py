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
        if student.referred_by:
            return False  # уже привязан

        result = await session.execute(
            select(User).where(User.tg_id == teacher_tg_id)
        )
        teacher = result.scalar_one_or_none()
        if not teacher or teacher.id == student.id:
            return False

        student.referred_by = teacher.id
        # +5% от мощи учителя
        student.teacher_power_bonus = int(teacher.combat_power * 0.05)

        # Учитель получает бонусные монеты за ученика
        teacher.nh_coins += 1000

        # Проверяем нет ли уже записи
        existing = await session.execute(
            select(Referral).where(Referral.student_id == student.id)
        )
        if not existing.scalar_one_or_none():
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

    async def get_referral_stats(
        self, session: AsyncSession, user: User
    ) -> dict:
        """Статистика реферальной системы для пользователя."""
        students = await self.get_students(session, user.id)
        teacher = await self.get_teacher(session, user)

        # Суммарно заработано с учеников
        total_earned_r = await session.execute(
            select(Referral).where(Referral.teacher_id == user.id)
        )
        referrals = total_earned_r.scalars().all()
        total_earned = sum(r.total_earned for r in referrals)

        return {
            "students_count": len(students),
            "students": students[:5],
            "teacher": teacher,
            "total_earned": total_earned,
            "power_bonus": user.teacher_power_bonus,
        }


referral_service = ReferralService()