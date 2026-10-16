from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class StorageCell(Base):
    """Открытая ячейка хранения (строка есть — ячейка куплена). Содержимое — один вид вещи:
    ресурс или отряд статистов (`constant/storage`). Лежащее в ячейке не на балансе и не в
    лагерях — его не украсть саботажем, не забрать войной и не потерять в бою. Плата копится
    с `fee_from`, пока ячейка не пуста."""

    __tablename__ = "storage_cells"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_kind: Mapped[str] = mapped_column(String(8), nullable=False, default="", server_default="")
    item_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    fee_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
