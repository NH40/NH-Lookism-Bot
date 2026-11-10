from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class EmpireEvent(Base):
    """Ивент императора для подданных (пользователь 2026-11-10, `services/empire/events`).

    Подданные — игроки в городах этого императора на момент действия (не снимок). Всё, что
    раздаётся, оплачено заранее из NHCoin императора: `pool` — остаток монет фонда, `units` —
    остаток статистов, `slots` — сколько ещё раз можно забрать (раздачи). По окончании остаток
    возвращается императору. Один активный ивент каждого вида у императора (частичный индекс)."""

    __tablename__ = "empire_events"
    __table_args__ = (
        Index("uq_empire_events_active_kind", "emperor_id", "kind", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_empire_events_status_ends", "status", "ends_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    emperor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active", server_default="active")
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    pool: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    spent: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    claims: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmpireEventClaim(Base):
    """Кто забрал (раздачи — один раз, ежедневный подарок — раз в сутки UTC): PK — защита от
    двойного клика (правило 1)."""

    __tablename__ = "empire_event_claims"

    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("empire_events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
