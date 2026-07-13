from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FameFragment(Base):
    """Один экземпляр фрагмента сета Кузницы славы — на весь сервер только одна строка
    на каждый fragment_key. owner_user_id = NULL значит фрагмент ещё не выкован."""
    __tablename__ = "fame_fragments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fragment_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    forged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
