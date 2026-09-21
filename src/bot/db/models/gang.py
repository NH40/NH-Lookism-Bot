from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Gang(Base):
    """Банда игрока — raw-notes «Карта»: «банда начинается с названия». Одна банда на
    игрока (1:1, `user_id` — сразу PK, без суррогатного ключа — тот же приём, что у
    `User.id`) — не путать с `клан` (домен `clan`, отдельная многопользовательская
    сущность, вкладка нижней навигации). Пока только название — состав (9 позиций),
    уникальная коллекция, статисты/лагеря появятся здесь по мере реализации
    соответствующих доменов (`recruit`/`extra`/`card`), не все разом.
    """

    __tablename__ = "gangs"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True, autoincrement=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
