from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RaidSession(Base):
    """Активный рейд игрока на босса."""
    __tablename__ = "raid_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    boss_id: Mapped[str] = mapped_column(String(32), nullable=False)
    clan_id: Mapped[str] = mapped_column(String(32), nullable=False)
    damage_dealt: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    fragments_earned: Mapped[int] = mapped_column(Integer, default=0)