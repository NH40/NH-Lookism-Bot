from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ActivePotion(Base):
    __tablename__ = "active_potions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    potion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Types: "power" | "wealth" | "influence" | "training" | "luck"
    bonus_value: Mapped[int] = mapped_column(Integer, default=0)  # % bonus
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)