"""Заявка на район после перехода в другую лигу (пользователь 2026-11-23).

Переехавший игрок получает свои районы на карте новой лиги, если они там свободны. Занятый другим игроком район —
заявка: здания с прошлого района отложены (`buildings`), у игрока 24 часа на бесплатный вызов. Победа — район и
здания; проигрыш или истёк срок — здания возвращаются NHCoin по базовой цене постройки."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class LeagueClaim(Base):
    __tablename__ = "league_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    district_id: Mapped[int] = mapped_column(Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    buildings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")  # тип → сколько
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open", server_default="open", index=True)
    challenge_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
