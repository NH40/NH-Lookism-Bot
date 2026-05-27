from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Payment(Base):
    """История платежей YooKassa (Telegram Payments)."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tg_payment_charge_id: Mapped[str | None] = mapped_column(String(128))
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(128))
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    nh_donate_credited: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
