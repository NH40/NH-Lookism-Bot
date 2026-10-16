from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class EmperorTaxOverride(Base):
    """Персональная ставка налога императора для конкретного игрока (пользователь
    2026-10-01: «настроить под конкретного игрока процент — одним дороже, другим дешевле»).
    Нет строки — действует общая ставка императора (`users.empire_tax_percent`). Строка
    привязана к паре (император, игрок): сменился император — старые ставки не действуют."""

    __tablename__ = "emperor_tax_overrides"

    emperor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Отдельный индекс: PK (emperor_id, user_id) не покрывает поиск/каскад по одному user_id.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
