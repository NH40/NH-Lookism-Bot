import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User

logger = logging.getLogger(__name__)


async def referral_power_tick():
    """Каждые 30 мин — обновляет бонус мощи от учителя для всех учеников."""
    try:
        async with AsyncSessionFactory() as session:
            # Загружаем всех студентов с referred_by
            rows = (await session.execute(
                select(User.id, User.referred_by).where(User.referred_by.isnot(None))
            )).all()

        if not rows:
            return

        # Одна сессия на весь тик; savepoint изолирует ошибки отдельных студентов
        async with AsyncSessionFactory() as session:
            async with session.begin():
                # Собираем все нужные ID — студентов и учителей
                student_ids = [r.id for r in rows]
                teacher_ids = list({r.referred_by for r in rows})
                all_ids = list(set(student_ids + teacher_ids))

                # Батч-загрузка всех участников в одном запросе
                users_result = await session.execute(
                    select(User).where(User.id.in_(all_ids))
                )
                users_map = {u.id: u for u in users_result.scalars().all()}

                from app.repositories.squad_repo import squad_repo

                for row in rows:
                    try:
                        async with session.begin_nested():
                            student = users_map.get(row.id)
                            teacher = users_map.get(row.referred_by)
                            if not student or not teacher:
                                continue

                            student_own = max(0, student.combat_power - student.teacher_power_bonus)
                            if student_own >= teacher.combat_power:
                                student.teacher_power_bonus = 0
                            else:
                                teacher_cap = int(teacher.combat_power * 0.05)
                                new_bonus = min(int(student_own * 0.20), teacher_cap)
                                student.teacher_power_bonus = max(student.teacher_power_bonus, new_bonus)

                            await squad_repo.update_user_combat_power(session, student)
                    except Exception as e:
                        logger.error(f"referral_power_tick student {row.id}: {e}")
    except Exception as e:
        logger.error(f"referral_power_tick error: {e}", exc_info=True)
