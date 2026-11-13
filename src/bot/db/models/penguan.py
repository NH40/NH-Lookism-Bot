"""Временные бафы родословной Пеньгуана (Подкуп, Казна, Золотая вербовка)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class PenguanBuff(Base):
    __tablename__ = "penguan_buffs"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    power: Mapped[float] = mapped_column(Float, nullable=False)


class PenguanFallen(Base):
    """Павшие последнего боя Пеньгуана — для выкупа (одна строка на игрока, перезаписывается)."""

    __tablename__ = "penguan_fallen"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    camp: Mapped[str] = mapped_column(String(16), nullable=False)
    rows: Mapped[list] = mapped_column(JSONB, nullable=False)
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
