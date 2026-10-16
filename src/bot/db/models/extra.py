from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.constant.extra import CAMP_ATTACK
from bot.db.base import Base


class Extra(Base):
    """Статисты игрока — СТОПКОЙ, не по одной строке на статиста (переработано
    2026-09-21 по прямому запросу пользователя: "могут быть сотни миллиардов этих
    самых статистов" — миллиарды строк на игрока физически нереализуемы, и
    поштучный случайный бросок при тренировке/бою на такой популяции невозможно
    посчитать). Одна строка — "все статисты игрока в таком-то лагере, с таким-то
    рангом, числом звёзд пробуждения и уровнем тренировки", `quantity` — сколько их
    (BigInteger — Integer столько не потянет, ~2.1 млрд потолок).

    `training_level` — сколько раз стопка успешно прошла этап 1 тренировки (мощь ×1.2
    каждый раз, см. `services/training`) — часть КЛЮЧА, а не отдельное поле мощи: мощь
    единицы всегда считается по формуле (`config/characteristic.extra_unit_power`),
    никогда не хранится поштучно.

    `camp` (лагерь атака/защита, raw-notes «Банда») — тоже часть ключа, NOT NULL с
    дефолтом "attack" (подтверждено пользователем 2026-09-29: новые статисты сразу в
    атаке, игрок сам перекидывает часть в защиту). Именно NOT NULL, а не nullable
    "не распределён": NULL ≠ NULL в уникальном индексе Postgres, и `ON CONFLICT`
    апсерт стопок просто перестал бы сливать одинаковые стопки.
    """

    __tablename__ = "extras"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "camp", "rank", "stars", "training_level", "school", "school_level", name="uq_extras_stack"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    camp: Mapped[str] = mapped_column(String(16), nullable=False, default=CAMP_ATTACK, server_default=CAMP_ATTACK)
    rank: Mapped[str] = mapped_column(String(8), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    training_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    # Школа учителя статистов и её уровень (пользователь 2026-10-03: учителя «позволяют
    # статистам выходить в школы и получать бафы»; `constant/school`). Часть ключа стопки —
    # бойцы разных школ бьются по-разному. "" / 0 — без школы.
    school: Mapped[str] = mapped_column(String(8), nullable=False, default="", server_default="")
    school_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
