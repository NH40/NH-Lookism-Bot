from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserCharacter(Base):
    __tablename__ = "user_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[str] = mapped_column(String(8), nullable=False)
    power: Mapped[int] = mapped_column(Integer, default=0)
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())