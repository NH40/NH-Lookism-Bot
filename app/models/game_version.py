from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GameVersion(Base):
    __tablename__ = "game_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    patch_notes: Mapped[str] = mapped_column(String(2048), default="")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())