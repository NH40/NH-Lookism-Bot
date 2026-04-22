from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SquadMember(Base):
    __tablename__ = "squad_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rank: Mapped[str] = mapped_column(String(8), nullable=False)  # E, D, C, B, A, S
    stars: Mapped[int] = mapped_column(Integer, default=0)  # 0-5
    base_power: Mapped[int] = mapped_column(Integer, default=0)