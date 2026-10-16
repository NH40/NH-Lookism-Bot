from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class DailyQuest(Base):
    """Ежедневное задание игрока: слот 1–10 дня (день — по Москве). Прогресс растёт от событий
    игры (`services/dev_quest.emit`), выполненное сразу даёт опыт Battle Pass (`completed_at`)."""

    __tablename__ = "daily_quests"
    __table_args__ = (
        UniqueConstraint("user_id", "day", "slot", name="uq_daily_quests_slot"),
        Index("ix_daily_quests_user_day_task", "user_id", "day", "task"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    task: Mapped[str] = mapped_column(String(16), nullable=False)
    target: Mapped[int] = mapped_column(BigInteger, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, nullable=False)
    progress: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyQuestState(Base):
    """Состояние дня игрока: рероллы (раз в день — либо все, либо до 2 замен) и сколько
    заданий выполнено (порядок для поощрения ×3/×2). Ленивый сброс по `day`."""

    __tablename__ = "daily_quest_states"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    full_reroll_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    swaps_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
