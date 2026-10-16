"""Системы развития — владение путями, уникальными техниками и гениальностями с уровнями
(`docs/design/development_systems.md`).

Одна таблица на систему, строка — (игрок, код, уровень). Владеть можно несколькими
(техники — у разных учителей, гениальности — прокрутом, пути — донатом), активна одна —
`users.active_path/active_technique/active_genius`. Родословная — колонками `users`
(она одна и выбирается навсегда).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class UserPath(Base):
    __tablename__ = "user_paths"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserTechnique(Base):
    __tablename__ = "user_techniques"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserGenius(Base):
    __tablename__ = "user_geniuses"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BattleMemory(Base):
    """Пути последних противников в PvP — для путей Копирования и Бесконечной техники
    (пользователь: «вспомнить пять последних противников»). Хранится не больше
    `PATH_MEMORY_SIZE` строк на игрока — старые удаляются при записи."""

    __tablename__ = "battle_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    opponent_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path_code: Mapped[str] = mapped_column(String(32), nullable=False)
    path_level: Mapped[int] = mapped_column(Integer, nullable=False)
    fought_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSchool(Base):
    """Учитель статистов у игрока (пользователь 2026-10-03): после квеста учителя на карте
    строка появляется с `owned=False` — учитель «появился в магазине»; покупка ставит
    `owned=True` — открываются занятия у него. Школа — `constant/school`."""

    __tablename__ = "user_schools"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    school: Mapped[str] = mapped_column(String(8), primary_key=True)
    owned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
