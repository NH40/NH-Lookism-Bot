from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.donate import SBP_STATUS_EXPIRED, SBP_STATUS_PENDING, SBP_STATUS_SUCCEEDED
from bot.db.models.donate import SbpPayment


async def create(
    session: AsyncSession, *, yookassa_id: str, user_id: int, amount_rub: int, confirmation_url: str,
    chat_id: int | None, message_id: int | None,
) -> SbpPayment:
    """Не коммитит."""
    row = SbpPayment(
        yookassa_id=yookassa_id, user_id=user_id, amount_rub=amount_rub, status=SBP_STATUS_PENDING,
        confirmation_url=confirmation_url, chat_id=chat_id, message_id=message_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, payment_id: int) -> SbpPayment | None:
    return await session.get(SbpPayment, payment_id)


async def mark_succeeded(session: AsyncSession, yookassa_id: str) -> SbpPayment | None:
    """Атомарный переход в succeeded (правило 1): вебхук, фоновая проверка и «Я оплатил»
    могут прийти одновременно — строку получит только первый. None — уже зачислено или
    счёта нет. Не коммитит (коммит — в `credit_payment`)."""
    result = await session.execute(
        update(SbpPayment)
        .where(SbpPayment.yookassa_id == yookassa_id, SbpPayment.status != SBP_STATUS_SUCCEEDED)
        .values(status=SBP_STATUS_SUCCEEDED)
        .returning(SbpPayment)
    )
    return result.scalar_one_or_none()


async def mark_open_as(session: AsyncSession, yookassa_id: str, status: str) -> SbpPayment | None:
    """pending/expired → `status` (отмена). Оплаченный счёт не трогает. Не коммитит."""
    result = await session.execute(
        update(SbpPayment)
        .where(SbpPayment.yookassa_id == yookassa_id, SbpPayment.status.in_((SBP_STATUS_PENDING, SBP_STATUS_EXPIRED)))
        .values(status=status)
        .returning(SbpPayment)
    )
    return result.scalar_one_or_none()


async def list_pending(session: AsyncSession, since: datetime, limit: int) -> list[SbpPayment]:
    rows = await session.scalars(
        select(SbpPayment)
        .where(SbpPayment.status == SBP_STATUS_PENDING, SbpPayment.created_at >= since)
        .order_by(SbpPayment.created_at)
        .limit(limit)
    )
    return list(rows)


async def expire_older(session: AsyncSession, before: datetime) -> int:
    """Счета старше окна проверки — в expired (бот перестаёт спрашивать ЮKassa). Не коммитит."""
    result = await session.execute(
        update(SbpPayment)
        .where(SbpPayment.status == SBP_STATUS_PENDING, SbpPayment.created_at < before)
        .values(status=SBP_STATUS_EXPIRED)
    )
    return result.rowcount or 0
