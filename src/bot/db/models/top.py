"""Топ игроков и кланов (модели): журнал выплат наград за сезон."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class SeasonTopPayout(Base):
    """Награды топа за сезон выданы. Ключ — `bp:<номер сезона Battle Pass>` (конец месяца) или
    `patch:<время>` (патч из админки); PK — гарантия «ровно один раз» при гонке двух процессов."""

    __tablename__ = "season_top_payouts"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
