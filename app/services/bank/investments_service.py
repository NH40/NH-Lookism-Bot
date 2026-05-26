"""
Инвестиции: до 3 вкладов одновременно, срок 1/3/6/12/24ч, доход 3/5/10/15/20%.
Максимальный вклад: 200 000 000 NHCoin.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.bank import Investment
from app.models.user import User
from app.constants.bank import INVEST_MAX_SLOTS, INVEST_MAX_DEPOSIT, INVEST_DURATION_OPTIONS

logger = logging.getLogger(__name__)

MAX_INVESTMENTS  = INVEST_MAX_SLOTS
MAX_DEPOSIT      = INVEST_MAX_DEPOSIT
DURATION_OPTIONS = INVEST_DURATION_OPTIONS


class InvestmentsService:

    # ── Активные вклады ───────────────────────────────────────────────────────

    async def get_active(
        self, session: AsyncSession, user_id: int
    ) -> list[Investment]:
        r = await session.execute(
            select(Investment).where(
                and_(Investment.user_id == user_id, Investment.is_withdrawn == False)
            ).order_by(Investment.started_at)
        )
        return r.scalars().all()

    # ── Открыть вклад ─────────────────────────────────────────────────────────

    async def create(
        self, session: AsyncSession, user: User, amount: int, duration_hours: int
    ) -> tuple[bool, str]:
        """
        Создать вклад.

        !! SELECT FOR UPDATE блокирует строку пользователя — параллельный
        запрос будет ждать и после разблокировки увидит актуальный счёт/лимит.
        """
        if duration_hours not in DURATION_OPTIONS:
            return False, "❌ Неверный срок вклада."
        if amount < 1000:
            return False, "❌ Минимальный вклад: 1 000 NHCoin."
        if amount > MAX_DEPOSIT:
            return False, f"❌ Максимальный вклад: {MAX_DEPOSIT:,} NHCoin."

        # Блокируем строку пользователя — никакой второй запрос не войдёт
        # в критическую секцию пока мы не закоммитим транзакцию.
        locked_user = await session.scalar(
            select(User).where(User.id == user.id).with_for_update()
        )
        if not locked_user:
            return False, "❌ Пользователь не найден."

        if locked_user.nh_coins < amount:
            return False, "❌ Недостаточно NHCoin."

        # Перечитываем вклады под блокировкой
        active = await self.get_active(session, locked_user.id)
        if len(active) >= MAX_INVESTMENTS:
            return False, f"❌ Максимум {MAX_INVESTMENTS} вклада одновременно."

        interest_pct = DURATION_OPTIONS[duration_hours]
        now = datetime.now(timezone.utc)

        locked_user.nh_coins -= amount
        user.nh_coins = locked_user.nh_coins  # синхронизируем внешний объект
        inv = Investment(
            user_id=locked_user.id,
            amount=amount,
            duration_hours=duration_hours,
            interest_pct=interest_pct,
            started_at=now,
            matures_at=now + timedelta(hours=duration_hours),
        )
        session.add(inv)
        await session.flush()
        return True, ""

    # ── Забрать созревший вклад ───────────────────────────────────────────────

    async def withdraw(
        self, session: AsyncSession, user: User, investment_id: int
    ) -> tuple[bool, str, int]:
        """
        Возвращает (ok, error_msg, payout).
        payout = amount + проценты.

        !! SELECT FOR UPDATE блокирует строку вклада — двойная выплата невозможна.
        """
        # Блокируем конкретную строку вклада — параллельный запрос будет ждать.
        # После разблокировки второй запрос увидит is_withdrawn=True и откажет.
        inv = await session.scalar(
            select(Investment)
            .where(Investment.id == investment_id, Investment.user_id == user.id)
            .with_for_update()
        )
        if not inv:
            return False, "❌ Вклад не найден.", 0
        if inv.is_withdrawn:
            return False, "❌ Вклад уже закрыт.", 0

        now = datetime.now(timezone.utc)
        if now < inv.matures_at:
            remaining = int((inv.matures_at - now).total_seconds())
            from app.utils.formatters import fmt_ttl
            return False, f"❌ Вклад ещё не созрел. Осталось: {fmt_ttl(remaining)}.", 0

        payout = inv.amount + int(inv.amount * inv.interest_pct / 100)
        user.nh_coins += payout
        inv.is_matured = True
        inv.is_withdrawn = True
        await session.flush()
        return True, "", payout

    # ── Тик: уведомить о созревших вкладах ───────────────────────────────────

    async def maturity_tick(self, session: AsyncSession) -> list[Investment]:
        """
        Пометить созревшие вклады (is_matured=True) и вернуть список для уведомлений.
        Вклад НЕ выплачивается автоматически — игрок должен нажать «Забрать».
        """
        now = datetime.now(timezone.utc)
        r = await session.execute(
            select(Investment).where(
                and_(
                    Investment.is_matured == False,
                    Investment.is_withdrawn == False,
                    Investment.matures_at <= now,
                    Investment.notif_sent == False,
                )
            )
        )
        matured = r.scalars().all()
        for inv in matured:
            inv.is_matured = True
            inv.notif_sent = True
        await session.flush()
        return matured


investments_service = InvestmentsService()
