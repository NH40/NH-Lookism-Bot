from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PokerTable(Base):
    __tablename__ = "poker_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    small_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    big_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="waiting")
    # waiting | active | finished | cancelled

    pot: Mapped[int] = mapped_column(BigInteger, default=0)
    rake_taken: Mapped[int] = mapped_column(BigInteger, default=0)

    community_cards: Mapped[str] = mapped_column(String(64), default="[]")  # json [[rank,suit],...]
    current_round: Mapped[str] = mapped_column(String(16), default="preflop")
    # preflop | flop | turn | river | showdown

    current_bet: Mapped[int] = mapped_column(BigInteger, default=0)
    last_raise_amount: Mapped[int] = mapped_column(BigInteger, default=0)

    dealer_seat: Mapped[int] = mapped_column(Integer, default=0)
    current_seat: Mapped[int] = mapped_column(Integer, default=0)

    action_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PokerPlayer(Base):
    __tablename__ = "poker_players"
    __table_args__ = (
        UniqueConstraint("table_id", "user_id", name="uq_poker_player_table_user"),
        UniqueConstraint("table_id", "seat_index", name="uq_poker_player_table_seat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)

    stack: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hole_cards: Mapped[str] = mapped_column(String(32), default="[]")  # json [[r,s],[r,s]]

    status: Mapped[str] = mapped_column(String(16), default="active")
    # active | folded | all_in

    current_round_bet: Mapped[int] = mapped_column(BigInteger, default=0)
    total_bet: Mapped[int] = mapped_column(BigInteger, default=0)
    has_acted: Mapped[bool] = mapped_column(Boolean, default=False)

    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
