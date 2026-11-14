from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Bank(Base):
    """Банк игрока (один на игрока): свободный капитал и условия кредитов. Выданное — в `bank_loans`.

    Виды кредита (2026-11-14, банки v2): фиксированный (`fixed_rate` — разово к сумме) и почасовой (`hourly_rate` — каждый
    час на остаток). NULL — вид выключен. `rate` — прежняя дневная ставка, осталась только у старых кредитов."""

    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    capital: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # свободный: выдать или забрать
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # legacy: доля в день
    fixed_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    penalty_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # пеня в час на долг во время заморозки
    min_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_days: Mapped[int] = mapped_column(Integer, nullable=False)
    lent_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # выдано за всё время
    earned_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # получено процентов и пени
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankMember(Base):
    """Участник банка («мини-клан»): пополняет капитал и одобряет заявки. Игрок — участник не больше одного банка."""

    __tablename__ = "bank_members"

    bank_id: Mapped[int] = mapped_column(Integer, ForeignKey("banks.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, unique=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankLoan(Base):
    """Заявка → договор → кредит. Статусы — `constant/bank` (pending → offered → active → frozen → slave / repaid).
    Платёж гасит сначала пеню, потом проценты, потом тело. Закрытые остаются историей."""

    __tablename__ = "bank_loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("banks.id", ondelete="SET NULL"), nullable=True)
    lender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    borrower_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="daily")
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # взято
    principal: Mapped[int] = mapped_column(BigInteger, nullable=False)  # остаток тела
    interest: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # начислено и не погашено
    penalty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # пеня, не погашенная
    penalty_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # пени начислено всего (потолок)
    paid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # всего погашено (в т.ч. конфискацией)
    rate: Mapped[float] = mapped_column(Float, nullable=False)  # ставка своего вида (fixed — разово, hourly — в час)
    penalty_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)  # условия, дописанные банкиром
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    offer_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accrued_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # legacy daily
    accrued_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # hourly
    penalty_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slave_pool: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # удержано с дохода, ещё не в капитале
    frozen_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_bank_loans_borrower_status", "borrower_id", "status"),
        Index("ix_bank_loans_bank_status", "bank_id", "status"),
        Index("ix_bank_loans_status_due", "status", "due_at"),
    )

    @property
    def debt(self) -> int:
        return self.principal + self.interest + self.penalty
