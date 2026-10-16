from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class District(Base):
    """Район города — raw-notes «Карта»: «во всех районах есть боты с небольшим
    количеством мощи, однако если район уже захвачен — начинается сражение за район с
    другим игроком». `owner_id IS NULL` — район держат боты (их армия НЕ хранится в БД,
    она виртуальная и считается из размера города, см. `config/game.BOT_DISTRICT_ARMY` —
    ботам не нужна персистентность потерь, каждый бой они выходят в полном составе).

    Засевается `manager.py seed` из `cities.district_count` одним `INSERT ... SELECT
    generate_series` (см. `db/repositories/district.seed_districts`) — `(city_id,
    number)` уникален, повторный сид ничего не дублирует.
    """

    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("city_id", "number", name="uq_districts_city_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("cities.id"), index=True, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
