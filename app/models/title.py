from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    achievement_id: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserDonatTitle(Base):
    __tablename__ = "user_donat_titles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title_id: Mapped[str] = mapped_column(String(64), nullable=False)
    set_id: Mapped[str | None] = mapped_column(String(64))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    granted_by: Mapped[int | None] = mapped_column(BigInteger)