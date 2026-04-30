from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class KingBot(Base):
    __tablename__ = "king_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    power: Mapped[int] = mapped_column(BigInteger, default=10000)
    districts_total: Mapped[int] = mapped_column(Integer, default=16)
    districts_captured: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_defeated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )