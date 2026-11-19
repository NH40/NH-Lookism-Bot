"""Лига-обучение (модель, пользователь 2026-11-19): одна строка на игрока — шаг гайда и личная учебная карта.

`status`: `legacy` — игрок был до обучения (может пройти добровольно), `active` — идёт, `done` — пройдено.
Обязательное обучение (новичок) запрещает бои за настоящую территорию, пока не пройдено.
Учебная карта — JSON в `map` (3 города, районы, здания), после выпуска стирается.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class TutorialRun(Base):
    __tablename__ = "tutorial_runs"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    voluntary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    map: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    base: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)  # что было у игрока на старте шага (для проверок)
    accrued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # доход учебных зданий
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
