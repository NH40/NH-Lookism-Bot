from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Bank(Base):
    """Банк игрока (один на игрока): свободный капитал и условия кредитов. Выданное — в `bank_loans`."""

    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    capital: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # свободный: выдать или забрать
    rate: Mapped[float] = mapped_column(Float, nullable=False)  # доля в день (0.05 = 5%)
    min_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_days: Mapped[int] = mapped_column(Integer, nullable=False)
    lent_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # выдано за всё время
    earned_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # получено процентов
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankLoan(Base):
    """Кредит. Проценты капают раз в сутки на остаток тела до срока; платёж гасит сначала проценты, потом тело.
    Закрытые (погашен/списан) остаются историей."""

    __tablename__ = "bank_loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("banks.id", ondelete="SET NULL"), nullable=True)
    lender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    borrower_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # взято
    principal: Mapped[int] = mapped_column(BigInteger, nullable=False)  # остаток тела
    interest: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # начислено и не погашено
    paid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # всего погашено (в т.ч. конфискацией)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accrued_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # сколько суток процентов начислено
    frozen_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_bank_loans_borrower_status", "borrower_id", "status"),
        Index("ix_bank_loans_bank_status", "bank_id", "status"),
        Index("ix_bank_loans_status_due", "status", "due_at"),
    )

    @property
    def debt(self) -> int:
        return self.principal + self.interest
