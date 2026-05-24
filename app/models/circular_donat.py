from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserCircularDonat(Base):
    """Хранит сколько кругов у игрока по каждому круговому донату."""
    __tablename__ = "user_circular_donats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    donat_id: Mapped[str] = mapped_column(String(32), nullable=False)
    circles: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "donat_id", name="uq_user_circ_donat"),
    )
