from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SquadMember(Base):
    """Агрегированная запись отряда: одна строка на (user_id, rank, stars, base_power)
    с счётчиком count, а не одна строка на каждого бойца. base_power входит в ключ
    (а не выводится из rank на лету), чтобы пережившие ребаланс войска сохраняли
    свою историческую мощь отдельной группой, а не задним числом получали новую."""
    __tablename__ = "squad_members"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank: Mapped[str] = mapped_column(String(8), primary_key=True)  # E, D, C, B, A, S...
    stars: Mapped[int] = mapped_column(Integer, primary_key=True, default=0)  # 0-5
    base_power: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
