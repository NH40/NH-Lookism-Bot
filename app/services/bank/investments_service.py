"""Сервис инвестиций."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.bank import Investment
from app.services.bank.casino.common import CASINO_RESOURCES
from app.constants.bank import (
    INVEST_MAX_SLOTS,
    INVEST_MAX_DEPOSIT,
    INVEST_DURATION_OPTIONS,
    INVEST_DURATION_OPTIONS_OLD,
)
from app.utils.formatters import fmt_num

INVEST_RESOURCES = {k: v for k, v in CASINO_RESOURCES.items() if k != "squad"}

MAX_INVESTMENTS = INVEST_MAX_SLOTS
MAX_DEPOSIT = INVEST_MAX_DEPOSIT


def get_interest_pct(resource: str, hours: int) -> float | None:
    """Возвращает процент для ресурса.
    Для NHCoin — увеличенные в 4 раза.
    Для остальных — старые проценты (3, 5, 10, 15, 20).
    """
    if resource == "nh_coins":
        return INVEST_DURATION_OPTIONS.get(hours)
    return INVEST_DURATION_OPTIONS_OLD.get(hours)


class InvestmentsService:
    async def get_active(self, session: AsyncSession, user_id: int) -> list[Investment]:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Investment).where(
                Investment.user_id == user_id,
                Investment.is_withdrawn == False,
                Investment.matures_at > now
            )
        )
        return result.scalars().all()

    async def create(
        self, session: AsyncSession, user: User, resource: str, amount: int, hours: int
    ) -> tuple[bool, str]:
        if resource not in INVEST_RESOURCES:
            return False, "❌ Этот ресурс нельзя вложить."

        balance = getattr(user, resource, 0)
        if amount > balance:
            return False, f"❌ Недостаточно {INVEST_RESOURCES[resource]}."

        active = await self.get_active(session, user.id)
        if len(active) >= MAX_INVESTMENTS:
            return False, f"❌ Максимум {MAX_INVESTMENTS} вкладов."
        if amount > MAX_DEPOSIT:
            return False, f"❌ Максимальная сумма: {fmt_num(MAX_DEPOSIT)}."

        pct = get_interest_pct(resource, hours)
        if pct is None:
            return False, "❌ Неверный срок."

        setattr(user, resource, balance - amount)

        now = datetime.now(timezone.utc)
        matures_at = now + timedelta(hours=hours)

        investment = Investment(
            user_id=user.id,
            resource=resource,
            amount=amount,
            duration_hours=hours,
            interest_pct=int(pct * 10) // 1,
            matures_at=matures_at,
        )
        session.add(investment)
        await session.flush()
        return True, ""

    async def withdraw(
        self, session: AsyncSession, user: User, investment_id: int
    ) -> tuple[bool, str, int]:
        inv = await session.get(Investment, investment_id)
        if not inv or inv.user_id != user.id:
            return False, "❌ Вклад не найден.", 0
        if inv.is_withdrawn:
            return False, "❌ Вклад уже получен.", 0
        if datetime.now(timezone.utc) < inv.matures_at:
            return False, "❌ Срок ещё не истёк.", 0

        pct = inv.interest_pct / 10.0
        payout = int(inv.amount * (1 + pct / 100))

        resource = inv.resource
        balance = getattr(user, resource, 0)
        setattr(user, resource, balance + payout)

        inv.is_withdrawn = True
        await session.flush()
        return True, "", payout

    # ── Для планировщика ──────────────────────────────────────────────────────

    async def maturity_tick(self, session: AsyncSession) -> list[dict]:
        """
        Проверяет созревшие вклады и помечает их как готовые к выводу.
        Возвращает список уведомлений для игроков.
        """
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Investment).where(
                Investment.is_withdrawn == False,
                Investment.is_matured == False,
                Investment.matures_at <= now
            )
        )
        matured = result.scalars().all()

        notifications = []
        for inv in matured:
            inv.is_matured = True
            pct = inv.interest_pct / 10.0
            payout = int(inv.amount * (1 + pct / 100))
            notifications.append({
                "user_id": inv.user_id,
                "investment_id": inv.id,
                "amount": inv.amount,
                "payout": payout,
                "resource": inv.resource,
            })

        await session.flush()
        return notifications


investments_service = InvestmentsService()