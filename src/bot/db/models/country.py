from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Country(Base):
    """Страна — 7 строк, засеянных один раз из `config/country.COUNTRIES` (см.
    `db/repositories/city.seed_countries`). Существует в БД (не только как статичный
    Python-список) ровно затем, чтобы `User.country_code`/`City.country_code` могли
    ссылаться на неё через FK — источник правды по составу списка всё равно
    `config/country`, эта таблица не редактируется через админку.
    """

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
