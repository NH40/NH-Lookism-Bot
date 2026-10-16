from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class CardPosition(Base):
    """Позиция отряда игрока (9 позиций, `constant/card.POSITIONS`) и стоящая на ней копия
    уника. PK `(user_id, position)` — на позиции ровно одна карта, гарантия на уровне БД.

    Копия на позиции изъята из армии (`card_stacks`): не участвует в сражениях и не может
    погибнуть, работает только навыком позиции (подтверждено 2026-09-30). Одна копия — одна
    позиция: карта с двумя позициями может стоять на обеих, только если копий две.
    """

    __tablename__ = "card_positions"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[str] = mapped_column(String(16), primary_key=True)
    card_code: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
