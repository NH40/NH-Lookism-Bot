from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class BpSeason(Base):
    """Сезон Battle Pass — 30 дней; следующий начинается сам, когда истёк (или админом раньше)."""

    __tablename__ = "bp_seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class BattlePass(Base):
    """Пасс игрока в сезоне (как в UAP): опыт, платная ветка, high-water mark забранного по
    веткам (сплошной префикс 1..N), дневной буст первых уровней (ленивый сброс по `boost_day`)."""

    __tablename__ = "battle_passes"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    season_id: Mapped[int] = mapped_column(Integer, ForeignKey("bp_seasons.id", ondelete="CASCADE"), primary_key=True)
    xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    claimed_free: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    claimed_premium: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    boost_levels: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    boost_day: Mapped[date | None] = mapped_column(Date, nullable=True)


class BattlePassClaim(Base):
    """Уровни, забранные вне очереди (с пропуском более ранних) — спарс-таблица, как в UAP."""

    __tablename__ = "battle_pass_claims"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    season_id: Mapped[int] = mapped_column(Integer, ForeignKey("bp_seasons.id", ondelete="CASCADE"), primary_key=True)
    track: Mapped[str] = mapped_column(String(8), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, primary_key=True)
