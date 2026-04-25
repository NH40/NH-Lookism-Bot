from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User


class UserRepo:

    async def get_by_tg_id(
        self, session: AsyncSession, tg_id: int
    ) -> User | None:
        result = await session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, session: AsyncSession, user_id: int
    ) -> User | None:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        tg_id: int,
        full_name: str,
        username: str | None = None,
        gang_name: str | None = None,
    ) -> User:
        user = User(
            tg_id=tg_id,
            full_name=full_name,
            username=username,
            gang_name=gang_name,
        )
        session.add(user)
        await session.flush()
        # Создаём мастерство сразу
        from app.models.skill import UserMastery
        mastery = UserMastery(user_id=user.id)
        session.add(mastery)
        await session.flush()
        return user

    async def get_or_create(
        self,
        session: AsyncSession,
        tg_id: int,
        full_name: str,
        username: str | None = None,
    ) -> tuple[User, bool]:
        user = await self.get_by_tg_id(session, tg_id)
        if user:
            # Обновляем имя/username
            user.full_name = full_name
            user.username = username
            await session.flush()
            return user, False
        user = await self.create(session, tg_id, full_name, username)
        return user, True

    async def get_top_by_power(
        self, session: AsyncSession, limit: int = 10
    ) -> list[User]:
        result = await session.execute(
            select(User)
            .order_by(User.combat_power.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_rank_by_power(
        self, session: AsyncSession, user_id: int
    ) -> int:
        from sqlalchemy import func
        user_r = await session.execute(
            select(User.combat_power).where(User.id == user_id)
        )
        my_power = user_r.scalar_one_or_none() or 0

        rank = await session.scalar(
            select(func.count(User.id)).where(
                User.combat_power > my_power
            )
        )
        return (rank or 0) + 1

    async def get_all_with_income(
        self, session: AsyncSession
    ) -> list[User]:
        """Все игроки у которых есть доход (для income_tick)."""
        result = await session.execute(
            select(User).where(User.income_per_minute > 0)
        )
        return result.scalars().all()

    async def get_all_ui_users(
        self, session: AsyncSession
    ) -> list[User]:
        """Игроки с УИ (для ultra_instinct_tick)."""
        result = await session.execute(
            select(User).where(User.ultra_instinct == True)
        )
        return result.scalars().all()

    async def get_players_in_city(
        self, session: AsyncSession, city_id: int, exclude_user_id: int
    ) -> list[User]:
        """Игроки в том же городе (для PvP в фазе банды)."""
        result = await session.execute(
            select(User).where(
                User.gang_city_id == city_id,
                User.id != exclude_user_id,
                User.phase == "gang",
            )
        )
        return result.scalars().all()

    async def get_fist_players(
        self, session: AsyncSession, exclude_user_id: int
    ) -> list[User]:
        """Все кулаки для PvP."""
        result = await session.execute(
            select(User).where(
                User.phase == "fist",
                User.id != exclude_user_id,
            )
        )
        return result.scalars().all()


user_repo = UserRepo()