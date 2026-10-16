from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.constant.extra import CAMP_ATTACK
from bot.db.base import Base


class CardStack(Base):
    """Уники в армии — стопка «карта × количество» в одном лагере (подтверждено
    пользователем 2026-09-30: дубликаты идут в армию, уников распределяют по лагерям и они
    гибнут как статисты). Тот же приём, что `extras`: одна строка на (игрок, карта, лагерь),
    не строка на копию.

    `card_code` — код из конфига (`config/card`), без FK: каталог уников живёт в конфиге,
    как и остальной статичный баланс. Копия, стоящая на позиции отряда, сюда НЕ входит —
    она в `card_positions` (не бьётся и не гибнет).
    """

    __tablename__ = "card_stacks"
    __table_args__ = (UniqueConstraint("user_id", "card_code", "camp", name="uq_card_stacks"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    card_code: Mapped[str] = mapped_column(String(64), nullable=False)
    camp: Mapped[str] = mapped_column(String(16), nullable=False, default=CAMP_ATTACK, server_default=CAMP_ATTACK)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
