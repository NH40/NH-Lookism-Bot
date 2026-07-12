from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketListing(Base):
    __tablename__ = "market_listings"
    __table_args__ = (
        Index("ix_market_listings_active", "is_sold", "is_cancelled", "item_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Тип товара
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # squad_member, character, tickets, path_points, mastery_points, ui_fragments

    item_amount: Mapped[int] = mapped_column(Integer, default=1)
    item_meta: Mapped[str | None] = mapped_column(String(256))
    # JSON строка с доп. данными (ранг статиста, имя персонажа и т.д.)

    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource: Mapped[str] = mapped_column(String(32), nullable=False, default="nh_coins")
    # в каком ресурсе продавец хочет получить оплату — ключ из CASINO_RESOURCES

    is_sold: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyer_id: Mapped[int | None] = mapped_column(Integer)


class MarketAuction(Base):
    __tablename__ = "market_auctions"
    __table_args__ = (
        Index("ix_market_auctions_active", "is_finished", "is_cancelled", "ends_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    item_amount: Mapped[int] = mapped_column(Integer, default=1)
    item_meta: Mapped[str | None] = mapped_column(String(256))

    resource: Mapped[str] = mapped_column(String(32), nullable=False, default="nh_coins")
    min_bid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_bid: Mapped[int] = mapped_column(BigInteger, default=0)  # 0 = ставок ещё не было
    high_bidder_id: Mapped[int | None] = mapped_column(Integer)

    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketAuctionBid(Base):
    __tablename__ = "market_auction_bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )