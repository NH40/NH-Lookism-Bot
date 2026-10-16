from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class DevQuest(Base):
    """Задание систем развития: квест учителя уникальной техники, «подтверждение
    убеждений» и квест на путь (`docs/design/development_systems.md`). Задания — действия
    в игре (`constant/dev_quest`), прогресс начисляют события из сервисов
    (`services/dev_quest.emit`) внутри их транзакций.

    `tasks` — {задание: сколько нужно}, `progress` — {задание: сколько сделано}. Один
    активный квест на (игрок, вид, ссылка) — частичный уникальный индекс."""

    __tablename__ = "dev_quests"
    __table_args__ = (
        Index(
            "uq_dev_quest_active",
            "user_id",
            "kind",
            "ref",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default="")
    tasks: Mapped[dict] = mapped_column(JSONB, nullable=False)
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
