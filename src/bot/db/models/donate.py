"""Донат (модели): платежи ЮKassa, покупки чёрного рынка, перенос доната из LBP 1.3."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Payment(Base):
    """Успешный платёж Telegram Payments. Идемпотентность зачисления — уникальный
    `telegram_charge_id` (Telegram может передоставить апдейт), как в UAP."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    telegram_charge_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    provider_charge_id: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    coins: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DonateUnlock(Base):
    """Покупка чёрного рынка: открытый за донат гений/путь/техника и купленный постоянный
    уровень (`level` — пол уровня, переживает сброс прогресса и патчи)."""

    __tablename__ = "donate_unlocks"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class Lbp1Donation(Base):
    """Донат игрока в LBP 1.3 (титулы + круги чёрного рынка + остаток NHDonate), посчитанный
    один раз при запуске 2.0. Ключ — Telegram id: игрок мог ещё не зарегистрироваться в 2.0,
    тогда коины придут при первом /start (`credited_at`)."""

    __tablename__ = "lbp1_donations"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    titles: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    circles: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
