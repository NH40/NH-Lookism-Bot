from datetime import datetime
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GaprenChallenge(Base):
    """Серия побед подряд над Гапрёном на этапе Императора — гейт пробуждения."""
    __tablename__ = "gapren_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    # 0..GAPREN_WINS_NEEDED, сбрасывается в 0 при поражении
    streak: Mapped[int] = mapped_column(Integer, default=0)

    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
