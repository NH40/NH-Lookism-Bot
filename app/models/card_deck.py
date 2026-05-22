from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserDeck(Base):
    """Активная колода игрока: до 5 слотов, каждый ссылается на UserCharacter.id."""
    __tablename__ = "user_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)        # 1-5
    char_id: Mapped[int] = mapped_column(Integer, nullable=False)     # FK → user_characters.id

    __table_args__ = (
        UniqueConstraint("user_id", "slot", name="uq_user_deck_slot"),
    )
