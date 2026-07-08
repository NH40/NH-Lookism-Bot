from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserCharacter(Base):
    __tablename__ = "user_characters"
    __table_args__ = (
        # Обмен/колода/слияние/походы фильтруют по (user_id, rank) и (user_id, character_id)
        Index("ix_user_characters_user_rank", "user_id", "rank"),
        Index("ix_user_characters_user_charid", "user_id", "character_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    character_id: Mapped[str] = mapped_column(String(256), nullable=False)
    rank: Mapped[str] = mapped_column(String(32), nullable=False)

    # base_power — оригинальная мощь из таблицы CHARACTERS (не изменяется)
    base_power: Mapped[int] = mapped_column(BigInteger, default=0)
    # power — эффективная мощь с учётом уровня (= base_power * LEVEL_MULTIPLIERS[level])
    # используется для расчёта боевой мощи в squad_repo
    power: Mapped[int] = mapped_column(BigInteger, default=0)

    # Уровень карточки: 0-3
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Telegram file_id для быстрой повторной отправки фото карточки
    tg_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True, default=None)

    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
