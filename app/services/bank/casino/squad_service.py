"""Сервис для депозита статистов в казино."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.squad_repo import squad_repo


class SquadCasinoService:
    """Работа со статистами в казино."""

    MIN_DEPOSIT = 5          # Минимальный депозит
    WIN_MULTIPLIER = 1.2     # Множитель выигрыша (x1.2)

    async def get_rank_counts(self, session: AsyncSession, user_id: int) -> dict[str, int]:
        """Возвращает {ранг: количество} доступных статистов."""
        groups = await squad_repo.get_groups(session, user_id)
        counts: dict[str, int] = {}
        for g in groups:
            if g.count > 0:
                counts[g.rank] = counts.get(g.rank, 0) + g.count
        return counts

    async def get_available_ranks(self, session: AsyncSession, user_id: int) -> list[str]:
        """Возвращает список рангов, которых >= MIN_DEPOSIT."""
        counts = await self.get_rank_counts(session, user_id)
        return [rank for rank, count in counts.items() if count >= self.MIN_DEPOSIT]

    async def deposit(self, session: AsyncSession, user: User, rank: str, amount: int) -> dict:
        """
        Депозит статистов в казино.
        Списание происходит сразу, возврат — только при выигрыше.
        """
        if amount < self.MIN_DEPOSIT:
            return {"ok": False, "msg": f"❌ Минимальный депозит: {self.MIN_DEPOSIT} статистов."}

        # Проверяем, что у игрока есть статисты этого ранга
        groups = await squad_repo.get_groups(session, user.id, rank=rank)
        total = sum(g.count for g in groups)
        if total < amount:
            return {"ok": False, "msg": f"❌ У вас только {total} статистов ранга {rank}."}

        deposited = amount
        # Списываем статистов
        for g in groups:
            take = min(g.count, amount)
            if take > 0:
                await squad_repo.add_count(session, user.id, g.rank, g.stars, -take, base_power=g.base_power)
                amount -= take
            if amount <= 0:
                break

        await squad_repo.update_user_combat_power(session, user)
        await session.flush()

        return {"ok": True, "rank": rank, "amount_deposited": deposited}

    async def win(self, session: AsyncSession, user: User, rank: str, amount: int) -> dict:
        """
        Выигрыш: возвращаем депозит + 20% сверху (округление в меньшую сторону).
        """
        bonus = int(amount * self.WIN_MULTIPLIER)  # округление в меньшую сторону
        total_return = amount + bonus

        # Спрашиваем конфиг ранга для base_power
        from app.data.squad import RANKS_BY_ID
        rank_cfg = RANKS_BY_ID.get(rank)
        if not rank_cfg:
            return {"ok": False, "msg": "❌ Ранг не найден."}

        # Начисляем статистов (звёзды 0, как новые)
        await squad_repo.add_count(session, user.id, rank, 0, total_return, base_power=rank_cfg.base_power)
        await squad_repo.update_user_combat_power(session, user)
        await session.flush()

        return {"ok": True, "rank": rank, "returned": total_return, "bonus": bonus}

    async def lose(self, session: AsyncSession, user: User, rank: str, amount: int) -> dict:
        """Проигрыш: статисты уже списаны, просто фиксируем потерю."""
        return {"ok": True, "rank": rank, "lost": amount}


squad_casino_service = SquadCasinoService()