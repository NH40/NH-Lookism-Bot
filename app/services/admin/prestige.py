from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class AdminPrestigeMixin:

    async def give_prestige(self, session: AsyncSession, user: User, amount: int = 1) -> None:
        """Добавляет пробуждения игроку с бонусами как при обычном пробуждении."""
        for _ in range(amount):
            if user.prestige_level >= 10:
                break
            user.prestige_level += 1
            user.prestige_income_bonus += 5
            user.prestige_recruit_bonus += 5
            user.prestige_train_bonus += 5
            user.prestige_ticket_bonus += 1
            user.ticket_chance = min(getattr(user, "max_ticket_chance", 70), user.ticket_chance + 1)
        await session.flush()

    async def remove_prestige(self, session: AsyncSession, user: User, amount: int = 1) -> None:
        """Убирает пробуждения с откатом бонусов."""
        for _ in range(amount):
            if user.prestige_level <= 0:
                break
            user.prestige_level -= 1
            user.prestige_income_bonus = max(0, user.prestige_income_bonus - 5)
            user.prestige_recruit_bonus = max(0, user.prestige_recruit_bonus - 5)
            user.prestige_train_bonus = max(0, user.prestige_train_bonus - 5)
            user.prestige_ticket_bonus = max(0, user.prestige_ticket_bonus - 1)
            user.ticket_chance = max(25, user.ticket_chance - 1)
        await session.flush()
