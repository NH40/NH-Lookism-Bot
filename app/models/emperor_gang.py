from datetime import datetime
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class EmperorGangRecord(Base):
    """Отслеживает победы игрока над группировками на этапе Императора."""
    __tablename__ = "emperor_gang_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gang_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Сколько раз побеждена группировка (мощь растёт на 20% за каждую победу)
    defeat_count: Mapped[int] = mapped_column(Integer, default=0)

    # КД — до этого времени атака невозможна
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
