"""Отчёты разведки (модель): снимок того, что разведчик увидел о цели (навыки позиции
Разведки против Безопасности цели). Разведка — отдельный этап по кнопке, без КД; отчёт
хранится, пока его не обновит новая разведка той же цели (пользователь 2026-10-16)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class ScoutReport(Base):
    __tablename__ = "scout_reports"

    viewer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    target_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Поле → {"seen": exact|range|hidden, "value": …}; плюс "_target" — подпись цели.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
