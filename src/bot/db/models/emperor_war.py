from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.constant.empire import WAR_PENDING
from bot.db.base import Base


class EmperorWar(Base):
    """Война императоров (`docs/design/fist_emperor.md`, решения 2026-10-02): вызов с окном
    принятия. Принял — бой; не принял до `expires_at` — проиграл без боя (фоновый sweep).
    Два частичных уникальных индекса по висящим войнам — гарантия БД (правило 1): у
    нападающего одна исходящая, на защитника одна входящая одновременно. Итог (кто победил,
    сколько городов и NHCoin перешло) хранится для отчёта и истории."""

    __tablename__ = "emperor_wars"
    __table_args__ = (
        Index("uq_emperor_war_pending_attacker", "attacker_id", unique=True,
              postgresql_where=text(f"status = '{WAR_PENDING}'")),
        Index("uq_emperor_war_pending_defender", "defender_id", unique=True,
              postgresql_where=text(f"status = '{WAR_PENDING}'")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attacker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    defender_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=WAR_PENDING, server_default=WAR_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    attacker_won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cities_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    treasury_taken: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
