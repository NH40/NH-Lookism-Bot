from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class BattleLog(Base):
    """История боёв (`services/battle_log`). Без внешних ключей: нужна и после удаления участников."""

    __tablename__ = "battle_log"
    __table_args__ = (
        Index("ix_battle_log_attacker", "attacker_id", "id"),
        Index("ix_battle_log_defender", "defender_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    attacker_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    defender_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attacker_won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    a_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    a_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    a_dead: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    a_fled: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    d_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    d_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    d_dead: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    d_fled: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="", server_default="")
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="system", server_default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
