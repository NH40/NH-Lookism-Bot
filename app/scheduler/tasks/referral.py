import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User

logger = logging.getLogger(__name__)


async def referral_power_tick():
    """Каждые 30 мин — обновляет бонус мощи от учителя для всех учеников."""
    try:
        async with AsyncSessionFactory() as session:
            student_ids = list((await session.execute(
                select(User.id).where(User.referred_by.isnot(None))
            )).scalars())

        for student_id in student_ids:
            try:
                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        student = await session.get(User, student_id)
                        if not student or not student.referred_by:
                            continue
                        teacher = await session.get(User, student.referred_by)
                        if not teacher:
                            continue

                        from app.repositories.squad_repo import squad_repo

                        student_own = max(0, student.combat_power - student.teacher_power_bonus)
                        if student_own >= teacher.combat_power:
                            student.teacher_power_bonus = 0
                        else:
                            teacher_cap = int(teacher.combat_power * 0.05)
                            new_bonus = min(int(student_own * 0.20), teacher_cap)
                            # бонус только растёт (начальный 75k сохраняется)
                            student.teacher_power_bonus = max(student.teacher_power_bonus, new_bonus)

                        await squad_repo.update_user_combat_power(session, student)
            except Exception as e:
                logger.error(f"referral_power_tick student {student_id}: {e}")
    except Exception as e:
        logger.error(f"referral_power_tick error: {e}", exc_info=True)
