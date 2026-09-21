from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.constant.phase import PHASE_GANG
from bot.db.base import Base


class User(Base):
    """Игрок. `id` — Telegram user id (не суррогатный ключ), тот же паттерн, что в
    Universe Anime Planet — не плодит лишний join на каждый хендлер.

    Игровые поля добавляются по мере переноса каждого домена, не все разом. Пока —
    инфраструктурное ядро (middlewares/ban_check, middlewares/tech_mode, services/admin)
    + онбординг страны/города (домен `start`, см. raw-notes «Карта»): `country_code`/
    `city_id` выставляются ОДНИМ атомарным шагом через
    `db.repositories.user.set_country_and_city` (`UPDATE ... WHERE city_id IS NULL`,
    правило 1) — до этого момента выбор страны/города чисто презентационный (навигация
    между сообщениями в `handlers/start`, ничего не пишет в БД), поэтому оба поля либо
    оба NULL, либо оба заполнены. Повторный онбординг до появления кнопки "сбросить
    банду" в профиле (см. raw-notes «Фазы», ещё не реализована) невозможен. `phase` —
    банда/круг/кулак (см. `constant/phase`), все новые игроки начинают с банды.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    country_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.code"), nullable=True
    )
    city_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id"), nullable=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default=PHASE_GANG, server_default=PHASE_GANG)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
