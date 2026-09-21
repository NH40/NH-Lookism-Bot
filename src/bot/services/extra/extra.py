"""Статисты — стопки по (ранг, звёзды, уровень тренировки), лагерь атака/защита (сервис)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.characteristic import extra_unit_power
from bot.constant.characteristic import RANK_INDEX
from bot.db.repositories.extra import add_to_stack, list_stacks


async def recruit_into_stack(session: AsyncSession, user_id: int, rank: str) -> None:
    """Новый статист = +1 к стопке (ранг, 0 звёзд, 0 уровень тренировки) — НЕ коммитит
    сама (правило 10, вызывается из `services/recruit`, тот коммитит один раз)."""
    await add_to_stack(session, user_id=user_id, rank=rank, stars=0, training_level=0, quantity=1)


@dataclass(frozen=True, slots=True)
class ArmyStats:
    total_quantity: int
    total_power: int
    by_rank: list[tuple[str, int]]  # (ранг, количество), от лучшего ранга к худшему


async def get_army_stats(session: AsyncSession, user_id: int) -> ArmyStats:
    """Число стопок на игрока ограничено комбинаторикой (ранг×звёзды×уровень
    тренировки), а не размером армии — даже при "сотнях миллиардов" статистов
    агрегация здесь работает над МАЛЫМ числом строк-стопок, не над количеством
    единиц (правило 3 соблюдено: тяжёлое — сумма по стопкам в Python над десятками
    строк, а не по каждому юниту)."""
    stacks = await list_stacks(session, user_id)
    total = sum(s.quantity for s in stacks)
    total_power = sum(s.quantity * extra_unit_power(s.rank, s.stars, s.training_level) for s in stacks)

    by_rank_totals: dict[str, int] = {}
    for s in stacks:
        by_rank_totals[s.rank] = by_rank_totals.get(s.rank, 0) + s.quantity
    by_rank = sorted(by_rank_totals.items(), key=lambda kv: RANK_INDEX[kv[0]], reverse=True)

    return ArmyStats(total_quantity=total, total_power=total_power, by_rank=by_rank)
