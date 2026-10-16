"""Статисты как переносимый «предмет» — для ячеек хранения, биржи и ставок в казино.

Отряд статистов определяется ключом стопки без лагеря (ранг, звёзды, уровень тренировки,
школа и её уровень). Забирают бойцов сначала из лагеря защиты, потом из атаки — под
`FOR UPDATE` обеих стопок (правило 1); отдают в лагерь защиты. НЕ коммитят — шаги чужих
транзакций (правило 10).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.db.repositories.extra import add_to_stack, get_stack_for_update


@dataclass(frozen=True, slots=True)
class StatistKey:
    rank: str
    stars: int = 0
    training_level: int = 0
    school: str = ""
    school_level: int = 0

    def encode(self) -> str:
        """Компактная строка для `callback_data` и строк БД: `ранг:звёзды:уровень:школа:ур`."""
        return f"{self.rank}:{self.stars}:{self.training_level}:{self.school}:{self.school_level}"

    @classmethod
    def decode(cls, raw: str) -> "StatistKey":
        rank, stars, level, school, school_level = raw.split(":")
        return cls(rank, int(stars), int(level), school, int(school_level))

    def stack(self) -> dict:
        return {
            "rank": self.rank, "stars": self.stars, "training_level": self.training_level,
            "school": self.school, "school_level": self.school_level,
        }


async def take_statists(session: AsyncSession, user_id: int, key: StatistKey, amount: int) -> bool:
    """Забрать `amount` бойцов отряда (защита → атака). False — столько нет (ничего не тронуто)."""
    if amount <= 0:
        return False
    stacks = []
    for camp in (CAMP_DEFENSE, CAMP_ATTACK):
        stack = await get_stack_for_update(session, user_id=user_id, camp=camp, **key.stack())
        stacks.append((camp, stack.quantity if stack else 0))
    if sum(q for _, q in stacks) < amount:
        return False
    left = amount
    for camp, have in stacks:
        take = min(have, left)
        if take:
            await add_to_stack(session, user_id=user_id, camp=camp, quantity=-take, **key.stack())
            left -= take
    return True


async def give_statists(session: AsyncSession, user_id: int, key: StatistKey, amount: int, camp: str = CAMP_DEFENSE) -> None:
    if amount > 0:
        await add_to_stack(session, user_id=user_id, camp=camp, quantity=amount, **key.stack())
