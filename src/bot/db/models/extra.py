from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Extra(Base):
    """Статисты игрока — СТОПКОЙ, не по одной строке на статиста (переработано
    2026-09-21 по прямому запросу пользователя: "могут быть сотни миллиардов этих
    самых статистов" — миллиарды строк на игрока физически нереализуемы, и
    поштучный случайный бросок при тренировке на такой популяции невозможно
    посчитать). Одна строка — это "все статисты игрока с таким-то рангом, числом
    звёзд пробуждения и уровнем тренировки", `quantity` — сколько их (BigInteger — Integer
    столько не потянет, ~2.1 млрд потолок, а речь о сотнях миллиардов).

    `training_level` — сколько раз этот статист успешно прошёл этап 1 тренировки
    (мощь ×1.2 каждый раз, см. `services/training`) — часть КЛЮЧА стопки, а не
    отдельное поле мощи: мощь единицы всегда считается по формуле
    (`config/characteristic.extra_unit_power(rank, stars, training_level)`), НИКОГДА
    не хранится поштучно — иначе пришлось бы либо копить триллион разных чисел мощи,
    либо отслеживать историю каждого статиста по отдельности, что при таком масштабе
    невозможно.

    `camp` (лагерь атака/защита, raw-notes «Банда») НЕ включён в модель сейчас —
    само распределение по лагерям ещё не реализовано (действие экрана «Банда»), а
    добавлять nullable-поле в ключ стопки заранее означало бы либо ломать
    ON CONFLICT-апсерты (NULL не равен NULL в уникальном индексе Postgres), либо
    гадать с сентинел-значением до того, как появится реальный потребитель.
    """

    __tablename__ = "extras"
    __table_args__ = (
        UniqueConstraint("user_id", "rank", "stars", "training_level", name="uq_extras_stack"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    rank: Mapped[str] = mapped_column(String(8), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    training_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
