from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Deposit(Base):
    """Вклад: ресурс (`constant/resource`) на срок под процент. Строка живёт, пока вклад не
    забран — забранный удаляется (истории не копим)."""

    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    hours: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    matures_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
