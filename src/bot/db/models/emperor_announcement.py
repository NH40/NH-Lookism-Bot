from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class EmperorAnnouncement(Base):
    """Объявление императора игрокам его земель (пользователь 2026-11-06).

    Одна строка на объявление, а не на получателя: журнал игрока — объявления его города
    (`city_ids` — города императора на момент отправки), поэтому он не пропадает при смене
    императора и не растёт на число игроков. Имя — снимок: император мог потерять трон или
    удалить аккаунт. `recipients` — все, кто платил налог в момент отправки, `muted` — из них
    выключили объявления, `delivered` — Telegram принял сообщение (растёт по ходу рассылки)."""

    __tablename__ = "emperor_announcements"
    __table_args__ = (Index("ix_emperor_announcements_city_ids", "city_ids", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    emperor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    emperor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    city_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    muted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    delivered: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
