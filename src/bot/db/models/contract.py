from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class StatistContract(Base):
    """Наёмные статисты по контракту (магазин; пользователь 2026-10-02: «в магазине можно
    покупать статистов по контракту… на какое-то время»; родословная Джинчоля удешевляет
    контракт и продлевает срок). Отряд воюет в лагере атаки как обычные статисты и гибнет
    в боях (`quantity` уменьшается), но не тренируется и не переносится; после `expires_at`
    уходит (в бою не участвует, строки чистит фоновый проход)."""

    __tablename__ = "statist_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rank: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    # Лагерь (пользователь 2026-10-12: контрактники — обычные отряды, их можно переводить между
    # атакой и защитой; в роту клана, ячейки и на биржу — нельзя, они живут только здесь).
    camp: Mapped[str] = mapped_column(String(8), nullable=False, default="attack", server_default="attack")
