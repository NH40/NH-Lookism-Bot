from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class Business(Base):
    """Здание на районе — raw-notes «Бизнес»: «у игрока появился 1 район, на нём он может
    построить свой первый бизнес». Типы — `constant/business.BUSINESS_TYPES`.

    **Владельца у здания нет — владелец района и есть владелец бизнеса** (`districts.
    owner_id`). Поэтому при захвате района бизнесы уходят победителю без единой записи в
    эту таблицу (подтверждено пользователем 2026-09-29: «уходят победителю») — переносить
    нечего, меняется только `districts.owner_id`. Доход по-прежнему считается от набора
    зданий на районах игрока в момент начисления (см. `services/business.accrue` — перед
    сменой владельца начисление делается обоим, иначе новый владелец получил бы доход
    захваченных зданий задним числом).
    """

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Здание стоит на районе (`district_id`) ИЛИ, у императора, лежит во «владениях»
    # (`holder_id`, район освобождён): при коронации районы уходят ботам пустыми, а доход
    # зданий остаётся императору (пользователь 2026-10-01).
    district_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("districts.id"), index=True, nullable=True)
    holder_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # Город, где здание стояло до ухода во владения (коронация) — по нему владения переходят
    # победителю войны императоров вместе с городами (пользователь 2026-10-14). У старых
    # владений (до 2026-10-14) — NULL: они переходят пропорционально доле потерянных городов.
    origin_city_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
