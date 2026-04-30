from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketListing(Base):
    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Тип товара
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # squad_member, character, tickets, path_points, mastery_points, ui_fragments

    item_amount: Mapped[int] = mapped_column(Integer, default=1)
    item_meta: Mapped[str | None] = mapped_column(String(256))
    # JSON строка с доп. данными (ранг статиста, имя персонажа и т.д.)

    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyer_id: Mapped[int | None] = mapped_column(Integer)