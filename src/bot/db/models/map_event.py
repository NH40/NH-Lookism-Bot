from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class MapEvent(Base):
    """Событие на карте (`docs/design/development_systems.md`): босс (Ким Гапрен, Джинен,
    Элита) или учитель уникальной техники. Общее для всех игроков, живёт до `ends_at`;
    появляется случайно фоновым проходом (`services/event.spawn_due`)."""

    __tablename__ = "map_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    # Клановое событие (Сторожевая башня / Додзё клана) — видно только участникам клана;
    # NULL — общее для всех.
    clan_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), index=True, nullable=True)


class MapEventEntry(Base):
    """Участие игрока в событии: победил ли босса (одна победа на событие), законнектился ли
    с учителем. PK (событие, игрок) — гарантия «одна победа» на уровне БД вместе с
    `UPDATE ... WHERE won = false` (правило 1)."""

    __tablename__ = "map_event_entries"

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("map_events.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
