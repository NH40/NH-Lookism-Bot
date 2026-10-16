"""Реферальные кампании админа (модели): именная ссылка и визиты по ней."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # /start ref_<code>
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReferralVisit(Base):
    """Новый игрок, пришедший по кампании (один игрок — одна кампания навсегда)."""

    __tablename__ = "referral_visits"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    link_id: Mapped[int] = mapped_column(Integer, ForeignKey("referral_links.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
