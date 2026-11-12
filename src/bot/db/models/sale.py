from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class SaleEvent(Base):
    """«Пятница» (`services/sale`): идёт, пока `now() < ends_at` и не `stopped`."""

    __tablename__ = "sale_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    started_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SaleChoice(Base):
    """«Пятница избранных»: какие категории выбрал игрок."""

    __tablename__ = "sale_choices"

    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sale_events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False, default=list, server_default="{}")


class SalePurchase(Base):
    """Разовая покупка пятницы (смена/уровень родословной, пробуждение) — одна на игрока."""

    __tablename__ = "sale_purchases"

    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sale_events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
