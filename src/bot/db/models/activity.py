from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class ActivityLog(Base):
    """Журнал заметных действий игрока — бои, захваты, постройки, развитие. Его читают
    гений наблюдения («читать логи игроков… кто что делает, к чему готовится», пользователь
    2026-10-02) и метки пути Сенсорики. Готовая строка, а не JSON — бот одноязычный, а
    журнал только показывается. Хранится `ACTIVITY_KEEP_DAYS` дней (чистка фоновым проходом)."""

    __tablename__ = "activity_log"
    __table_args__ = (Index("ix_activity_log_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PlayerMark(Base):
    """Метка на игрока (путь Сенсорики, гений наблюдения): «накинуть метки на игроков и
    следить за их развитием». Сколько меток можно держать — `EconomyMods.marks`."""

    __tablename__ = "player_marks"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
