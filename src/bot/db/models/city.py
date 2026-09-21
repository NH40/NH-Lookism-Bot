from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class City(Base):
    """Город — засеян один раз из `config/city.CITY_SEEDS` (см.
    `db/repositories/city.seed_cities`). `district_count` — стартовый размер (4/8/16/32,
    см. `config/city`), НЕ текущее состояние захвата — владение районами живёт в домене
    `district` (ещё не реализован), не здесь.

    Уникальность по `(country_code, name)`, а не отдельный `code` — города 2.0.0 это
    реальные города, а не процедурные имена 1.0, коллизий имён внутри одной страны в
    сид-списке не бывает по построению.
    """

    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("country_code", "name", name="uq_cities_country_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    district_count: Mapped[int] = mapped_column(Integer, nullable=False)
