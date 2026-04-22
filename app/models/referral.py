from datetime import datetime
from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # FK → users.id
    student_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)  # FK → users.id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_earned: Mapped[int] = mapped_column(Integer, default=0)  # всего монет заработал учитель с этого ученика