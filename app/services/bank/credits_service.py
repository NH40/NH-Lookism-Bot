"""
Сервис кредитов: выдача, проверка блокировки, частичное погашение, снос банды.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.bank import BankCredit
from app.models.user import User
from app.constants.bank import (
    CREDIT_MAX, CREDIT_REPAY_FACTOR, CREDIT_BLOCK_HOURS,
    CREDIT_DELETE_HOURS, CREDIT_INCOME_MINUTES,
)

logger = logging.getLogger(__name__)

# Псевдонимы для обратной совместимости внутри модуля
MAX_CREDITS   = CREDIT_MAX
REPAY_FACTOR  = CREDIT_REPAY_FACTOR
BLOCK_HOURS   = CREDIT_BLOCK_HOURS
DELETE_HOURS  = CREDIT_DELETE_HOURS


class CreditsService:

    # ── Получение активных кредитов ────────────────────────────────────────────

    async def get_active_credits(self, session: AsyncSession, user_id: int) -> list[BankCredit]:
        r = await session.execute(
            select(BankCredit).where(
                and_(BankCredit.user_id == user_id, BankCredit.is_paid == False)
            ).order_by(BankCredit.taken_at)
        )
        return r.scalars().all()

    async def get_all_credits(self, session: AsyncSession, user_id: int) -> list[BankCredit]:
        r = await session.execute(
            select(BankCredit).where(BankCredit.user_id == user_id)
            .order_by(BankCredit.taken_at.desc())
        )
        return r.scalars().all()

    # ── Взять кредит ──────────────────────────────────────────────────────────

    async def take_credit(
        self, session: AsyncSession, user: User, amount: int
    ) -> tuple[bool, str]:
        """
        Выдать кредит.
        Возвращает (ok, сообщение_об_ошибке_или_пустую_строку).
        """
        now = datetime.now(timezone.utc)

        # Проверка: не более MAX_CREDITS
        active = await self.get_active_credits(session, user.id)
        if len(active) >= MAX_CREDITS:
            return False, f"❌ Максимум {MAX_CREDITS} кредита одновременно."

        # Проверка суммы
        max_amount = user.income_per_minute * CREDIT_INCOME_MINUTES  # доход × N минут
        if max_amount <= 0:
            return False, "❌ У вас нет дохода. Постройте бизнес, чтобы взять кредит."
        if amount < 1000:
            return False, "❌ Минимальная сумма кредита: 1 000 NHCoin."
        if amount > max_amount:
            return False, f"❌ Максимальная сумма: {max_amount:,} NHCoin (доход × час)."

        # Проверка: у игрока нет просроченного кредита, требующего сноса банды
        for c in active:
            if c.is_gang_deleted:
                return False, "❌ Ваша банда уже снесена за долги. Выплатите кредит."

        due = int(amount * REPAY_FACTOR)
        credit = BankCredit(
            user_id=user.id,
            amount=amount,
            due_amount=due,
            paid_amount=0,
            block_at=now + timedelta(hours=BLOCK_HOURS),
            delete_at=now + timedelta(hours=DELETE_HOURS),
        )
        session.add(credit)
        user.nh_coins += amount
        await session.flush()
        return True, ""

    # ── Погашение кредита ─────────────────────────────────────────────────────

    async def repay_credit(
        self, session: AsyncSession, user: User, credit_id: int, amount: int
    ) -> tuple[bool, str]:
        """Погасить кредит частично или полностью."""
        r = await session.execute(
            select(BankCredit).where(
                and_(BankCredit.id == credit_id, BankCredit.user_id == user.id)
            )
        )
        credit = r.scalar_one_or_none()
        if not credit:
            return False, "❌ Кредит не найден."
        if credit.is_paid:
            return False, "❌ Кредит уже погашен."

        remaining = credit.due_amount - credit.paid_amount
        amount = min(amount, remaining)

        if user.nh_coins < amount:
            return False, f"❌ Недостаточно монет. Нужно: {amount:,} NHCoin."

        user.nh_coins -= amount
        credit.paid_amount += amount

        if credit.paid_amount >= credit.due_amount:
            credit.is_paid = True

        await session.flush()
        return True, ""

    # ── Проверка блокировки ───────────────────────────────────────────────────

    async def is_blocked(self, session: AsyncSession, user_id: int) -> bool:
        """Возвращает True, если есть просроченный (>3ч) неоплаченный кредит."""
        now = datetime.now(timezone.utc)
        r = await session.execute(
            select(BankCredit).where(
                and_(
                    BankCredit.user_id == user_id,
                    BankCredit.is_paid == False,
                    BankCredit.block_at <= now,
                )
            ).limit(1)
        )
        return r.scalar_one_or_none() is not None

    async def block_message(self, session: AsyncSession, user_id: int) -> str | None:
        """Возвращает текст ошибки если действие заблокировано, иначе None."""
        if await self.is_blocked(session, user_id):
            return (
                "🚫 <b>Действие заблокировано!</b>\n\n"
                "У вас есть просроченный кредит.\n"
                "Выплатите долг в <b>Банке → Кредиты</b>, чтобы продолжить."
            )
        return None

    # ── Полная выплата всех кредитов (патч) ──────────────────────────────────

    async def wipe_all_credits(self, session: AsyncSession) -> int:
        """Удалить все кредиты всех игроков (вызывается при патче)."""
        from sqlalchemy import delete
        res = await session.execute(delete(BankCredit))
        await session.flush()
        return res.rowcount


credits_service = CreditsService()
