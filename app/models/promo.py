from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # tickets, coins, ui_fragments, path_points, mastery_points
    reward_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PromoUse(Base):
    __tablename__ = "promo_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )