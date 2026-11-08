from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class ErrorLog(Base):
    """Ошибки и медленные операции бота и API (`services/error_log`). Одна строка на вид проблемы."""

    __tablename__ = "error_log"
    __table_args__ = (
        Index("uq_error_log_fingerprint", "fingerprint", unique=True),
        Index("ix_error_log_kind_seen", "kind", "last_seen"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(24), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    process: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # последний, у кого случилось
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    max_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
