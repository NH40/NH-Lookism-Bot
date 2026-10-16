from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.db.base import Base


class PokerTable(Base):
    """Стол PvP-покера (техасский холдем, перенос из 1.0). Раздачи идут подряд, пока за столом
    ≥2 игроков со стеком. Состояние раздачи — здесь и в `poker_players`; любое действие
    берёт строку стола `FOR UPDATE` — ходы двух игроков не сойдутся в одну раздачу."""

    __tablename__ = "poker_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    small_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    big_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="waiting", server_default="waiting", index=True)
    pot: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    community: Mapped[str] = mapped_column(String(64), nullable=False, default="[]", server_default="[]")
    street: Mapped[str] = mapped_column(String(16), nullable=False, default="preflop", server_default="preflop")
    current_bet: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    last_raise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    dealer_seat: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_seat: Mapped[int] = mapped_column(Integer, nullable=False, default=-1, server_default="-1")
    hand_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    action_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PokerPlayer(Base):
    __tablename__ = "poker_players"
    __table_args__ = (
        UniqueConstraint("table_id", "user_id", name="uq_poker_player_table_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("poker_tables.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    stack: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hole: Mapped[str] = mapped_column(String(32), nullable=False, default="[]", server_default="[]")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    round_bet: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    total_bet: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    acted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    leaving: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Сообщение-«экран стола» этого игрока: редактируется после каждого хода, а не спамит новыми.
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
