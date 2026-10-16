from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base

# Биржа (перенос из 1.0). Во всех трёх таблицах предмет — `item_kind` (`constant/resource.ITEM_*`)
# + `item_code` + `amount`, цена — `price_res` (код ресурса) + число. Предмет продавца лежит
# «в залоге» с момента выставления (на балансе его нет), строка удаляется по завершении сделки.


class ExchangeLot(Base):
    """Лот по фиксированной цене."""

    __tablename__ = "exchange_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    item_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_res: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExchangeAuction(Base):
    """Аукцион: ставка лидера тоже в залоге — перебили, вернулась."""

    __tablename__ = "exchange_auctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    item_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_res: Mapped[str] = mapped_column(String(16), nullable=False)
    min_bid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_bid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    bidder_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExchangeTrade(Base):
    """Прямой обмен: автор отдаёт предмет за цену конкретному игроку; предмет автора — в залоге,
    получатель платит при согласии."""

    __tablename__ = "exchange_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    to_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    item_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_res: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
