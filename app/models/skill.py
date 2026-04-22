from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserMastery(Base):
    """Мастерство: сила, скорость, выносливость, техника, богатство."""
    __tablename__ = "user_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    strength: Mapped[int] = mapped_column(Integer, default=0)    # 0-4
    speed: Mapped[int] = mapped_column(Integer, default=0)       # 0-4
    endurance: Mapped[int] = mapped_column(Integer, default=0)   # 0-4
    technique: Mapped[int] = mapped_column(Integer, default=0)   # 0-4
    wealth: Mapped[int] = mapped_column(Integer, default=0)      # 0-4


class UserPathSkills(Base):
    """Прокачанные навыки выбранного пути."""
    __tablename__ = "user_path_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)