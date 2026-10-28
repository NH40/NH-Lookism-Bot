from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.constant.district import CHALLENGE_PENDING, SCOPE_CITY, SCOPE_DISTRICT
from bot.db.base import Base


class DistrictChallenge(Base):
    """Вызов на район другого игрока (raw-notes «Карта»: «если это игрок, то ему приходит
    сообщение, и в течение 1 часа он должен начать сражение»). Принял — бой его лагеря
    атаки против лагеря атаки нападающего; не ответил до `expires_at` — фоновый sweep
    (`main.py`) проводит бой против его лагеря защиты (подтверждено пользователем
    2026-09-29).

    Два ЧАСТИЧНЫХ уникальных индекса по висящим (`status='pending'`) вызовам — гарантия
    на уровне БД, а не проверки в Python (правило 1): на один район — один висящий вызов,
    у одного нападающего — один исходящий (подтверждено пользователем: не даёт заспамить
    чужие районы). `defender_id` — владелец в момент вызова; если к бою район ему уже не
    принадлежит, вызов аннулируется (`resolution='void'`) без боя.

    **Масштаб (`scope`, 2026-09-29).** `district` — вызов банды за один район (`district_id`).
    `city` — вызов круга за ВСЕ районы защитника в городе (`city_id`, `district_id` пуст):
    победитель забирает те районы, что защитник держит в городе В МОМЕНТ боя (если ни
    одного не осталось — `void`). Третий частичный индекс — один висящий вызов за город на
    одного защитника; "один исходящий у нападающего" действует на оба масштаба сразу.
    """

    __tablename__ = "district_challenges"
    __table_args__ = (
        Index(
            "uq_challenge_pending_district",
            "district_id",
            unique=True,
            postgresql_where=text(f"status = '{CHALLENGE_PENDING}'"),
        ),
        Index(
            "uq_challenge_pending_city_defender",
            "city_id",
            "defender_id",
            unique=True,
            postgresql_where=text(f"status = '{CHALLENGE_PENDING}' AND scope = '{SCOPE_CITY}'"),
        ),
        # «Один исходящий у нападающего» снят 2026-10-28: КД — с момента вызова, вызывать можно
        # раз в КД, не дожидаясь ответа на предыдущий. Обычный индекс — для выборок по нападающему.
        Index("ix_challenge_attacker", "attacker_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default=SCOPE_DISTRICT, server_default=SCOPE_DISTRICT)
    district_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("districts.id"), index=True, nullable=True)
    city_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cities.id"), index=True, nullable=True)
    attacker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    defender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CHALLENGE_PENDING, server_default=CHALLENGE_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    attacker_won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
