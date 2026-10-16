from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class SabotageLog(Base):
    """Журнал саботажа против императора (`docs/design/fist_emperor.md`): кто, против кого,
    что пытался и чем кончилось. Императору саботажник анонимен — пуш и экран империи не
    показывают `saboteur_id`. Строка хранит его для будущего навыка Шпиона на позиции
    (пользователь 2026-10-01: раскрытие — один из навыков позиций, распределим, когда он
    пришлёт список навыков) — `revealed` выставит этот навык."""

    __tablename__ = "sabotage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emperor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    saboteur_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    card_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
