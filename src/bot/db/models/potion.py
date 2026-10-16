from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class UserPotion(Base):
    """Зелье игрока одного вида (`constant/potion`): последний выпитый тир и его окно
    действия. Строка на вид живёт и после окончания действия — окно нужно ленивому доходу
    бизнеса (зелье богатства считается только за пересечение с окном начисления), а
    `auto_tier` — настройка авто-зелья гения медицины (0 — выключено)."""

    __tablename__ = "user_potions"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    auto_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
