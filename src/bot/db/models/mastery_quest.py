from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.constant.mastery import QUEST_PENDING
from bot.db.base import Base


class MasteryQuest(Base):
    """Цепочка «Преодоление стены» игрока — одна строка на игрока, текущий этап (1..3).

    Жизненный цикл этапа: `pending` (условие выполнено, задание придёт в `available_at`,
    случайный момент 1–24 ч) → `active` (задания в работе, Том открывается после остальных;
    `tom_power` — снимок мощи на момент выдачи) → `trainer` (Том побеждён, у тренера можно
    купить 4 очка этапа: `points_bought`, невложенные — `points_free`) → вложены все 4 очка —
    следующий этап снова `pending`, после третьего — `complete`.
    """

    __tablename__ = "mastery_quests"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True, default=QUEST_PENDING, server_default=QUEST_PENDING
    )
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    tom_power: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    progress_trainings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    progress_pvp_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    equal_win: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    points_bought: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    points_free: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
