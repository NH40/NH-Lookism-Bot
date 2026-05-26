from datetime import datetime
from sqlalchemy import Integer, BigInteger, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BossAttack(Base):
    __tablename__ = "boss_attacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ID записи активного босса
    boss_record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Внутренний DB-ID пользователя (user.id)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Суммарный нанесённый урон
    damage_dealt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Количество ударов
    attack_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Время последней атаки
    last_attack_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("boss_record_id", "user_id", name="uq_boss_attack_user"),
    )
