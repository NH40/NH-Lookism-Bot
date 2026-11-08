from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class PlayerLedger(Base):
    """Журнал всего имущества и состояния игрока (пользователь 2026-11-08: «все аспекты журнала и логов»; у игрока
    пропали 500 млн, и по старым логам было не понять куда). Строки пишут ТОЛЬКО триггеры Postgres в той же
    транзакции, что и изменение: откат убирает и запись, забыть записать невозможно.

    `user_id` без внешнего ключа: журнал нужен и после удаления аккаунта, а каскадное удаление армии иначе падало
    бы на записи в журнал уже удалённого игрока. Частые мелкие изменения сливаются в одну строку (`hits`)."""

    __tablename__ = "player_ledger"
    __table_args__ = (Index("ix_player_ledger_user_id_desc", "user_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asset: Mapped[str] = mapped_column(String(24), nullable=False)
    item: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    balance: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    reason: Mapped[str] = mapped_column(String(24), nullable=False, default="", server_default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="system", server_default="system")
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
