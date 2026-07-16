"""Модель активного/завершённого похода."""
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaigns_status_ends_at", "status", "ends_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # ── Параметры похода ──────────────────────────────────────────────────────
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)   # nh_coins / card_dust / …
    rank: Mapped[str] = mapped_column(String(4), nullable=False)             # E D C B A S
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)     # 2 / 3 / 6 / 12

    # ── Статисты ──────────────────────────────────────────────────────────────
    # JSON-список [rank, stars, base_power, count] — сколько бойцов из какой
    # группы squad_members зарезервировано под поход (squad_members хранит
    # агрегаты, а не отдельные строки на бойца, поэтому вместо списка ID хранится
    # разбивка по группам).
    statist_breakdown: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    statist_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # средняя мощь
    statist_rank: Mapped[str] = mapped_column(String(8), nullable=False, default="ERROR")  # ранг статистов

    # ── Временные метки ───────────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # ── Статус и результат (заполняются планировщиком) ────────────────────────
    # "active"   — поход идёт
    # "finished" — поход завершён, можно забрать
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resource_gained: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    statists_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Сколько статистов погибло (не вернулось)
    statists_lost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
