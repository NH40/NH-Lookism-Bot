from datetime import datetime
from sqlalchemy import Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class HorseShopEvent(Base):
    """Временное окно лавки коня — раз в 24-36 часов, на 2 часа."""
    __tablename__ = "horse_shop_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active / expired

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Когда появится следующая лавка (заполняется при закрытии текущей)
    next_spawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HorseShopPurchase(Base):
    """Сколько единиц конкретного товара купил игрок за конкретное событие (лимит 40/шт.)."""
    __tablename__ = "horse_shop_purchases"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "item_id", name="uq_horse_shop_purchase"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
