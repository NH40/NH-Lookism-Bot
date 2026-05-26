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
            # Обновляем имя/username только если они изменились,
            # иначе flush() на каждый запрос = лишний UPDATE для 5000 игроков
            if user.full_name != full_name or user.username != username:
                user.full_name = full_name
                user.username = username
                await session.flush()
            return user, False
        user = await self.create(session, tg_id, full_name, username)
        return user, True

    async def get_top_by_power(
        self, session: AsyncSession, limit: int = 10
    ) -> list:
        result = await session.execute(
            select(User.full_name, User.combat_power, User.phase, User.ultra_instinct)
            .order_by(User.combat_power.desc())
            .limit(limit)
        )
        return result.all()

    async def get_rank_by_power(
        self, session: AsyncSession, user_id: int
    ) -> int:
        from sqlalchemy import func
        user_r = await session.execute(
            select(User.combat_power, User.path_unique_2).where(User.id == user_id)
        )
        row = user_r.one_or_none()
        if not row:
            return 1
        my_power, is_hidden = row.combat_power or 0, bool(row.path_unique_2)

        if is_hidden:
            # Скрытность (путь Тени): показываем ранг среди всех (включая себя)
            rank = await session.scalar(
                select(func.count(User.id)).where(User.combat_power > my_power)
            )
        else:
            # Обычный ранг — считаем только видимых игроков
            rank = await session.scalar(
                select(func.count(User.id)).where(
                    User.combat_power > my_power,
                    User.path_unique_2.is_(False),
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
        from sqlalchemy import or_
        result = await session.execute(
            select(User).where(
                or_(
                    User.ultra_instinct == True,
                    User.ui_is_donat == True,
                )
            )
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