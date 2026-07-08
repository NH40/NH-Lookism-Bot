from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SquadMember(Base):
    __tablename__ = "squad_members"
    __table_args__ = (
        # Обмен/походы фильтруют по (user_id, rank) — отдельно от (user_id, stars)
        Index("ix_squad_members_user_rank", "user_id", "rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rank: Mapped[str] = mapped_column(String(8), nullable=False)  # E, D, C, B, A, S
    stars: Mapped[int] = mapped_column(Integer, default=0)  # 0-5
    base_power: Mapped[int] = mapped_column(BigInteger, default=0)