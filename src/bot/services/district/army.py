"""Армия игрока для боя — сборка лагеря и списание потерь (сервис).

Общие для всех боёв домена district (PvE района, бой за город, PvP, бой за трон, бой с
Томом): вынесено из `district.py`, чтобы модули боёв не импортировали друг друга по кругу.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.absolute import ABSOLUTES
from bot.config.characteristic import extra_unit_power, statist_unit_power
from bot.config.school import (
    SCHOOL_BLOCK_PER_LEVEL,
    SCHOOL_COUNTER_PER_LEVEL,
    SCHOOL_DODGE_PER_LEVEL,
    SCHOOL_FLEE_PER_LEVEL,
)
from bot.db.models.extra import Extra
from bot.db.repositories import card as card_repo
from bot.db.repositories import contract as contract_repo
from bot.db.repositories.extra import add_to_stack, list_stacks
from bot.services.card import card_power
from bot.services.characteristic import strength_power_multiplier
from bot.services.combat import CombatStack


# Вид стопки в ключе боевого движка — по нему `apply_losses` знает, из какой таблицы
# списывать погибших.
_KIND_EXTRA = "x"
_KIND_CARD = "u"
_KIND_CONTRACT = "c"  # наёмники по контракту (магазин, родословная Джинчоля)


def combat_stacks(stacks: Sequence[Extra]) -> list[CombatStack]:
    """Стопки статистов одного лагеря → армия для боевого движка. Ключ — (вид, ранг,
    звёзды, уровень тренировки, школа, уровень школы): лагерь у всех стопок одной стороны
    один и тот же. Школа учителя даёт стопке свою мощь и реакции (`config/school`)."""
    result = []
    for s in stacks:
        level = s.school_level if s.school else 0
        result.append(
            CombatStack(
                key=(_KIND_EXTRA, s.rank, s.stars, s.training_level, s.school, s.school_level),
                unit_power=statist_unit_power(s.rank, s.stars, s.training_level, s.school, s.school_level),
                quantity=s.quantity,
                dodge=SCHOOL_DODGE_PER_LEVEL.get(s.school, 0.0) * level,
                block=SCHOOL_BLOCK_PER_LEVEL.get(s.school, 0.0) * level,
                counter=SCHOOL_COUNTER_PER_LEVEL.get(s.school, 0.0) * level,
                flee=SCHOOL_FLEE_PER_LEVEL.get(s.school, 0.0) * level,
            )
        )
    return result


async def load_camp(session: AsyncSession, user_id: int, camp: str, *, for_update: bool) -> list[CombatStack]:
    """Весь лагерь игрока для боя: статисты И уники из армии (подтверждено 2026-09-30:
    копии уников вне отряда бьются и гибнут как статисты; уники на позициях отряда в бою не
    участвуют — их в `card_stacks` нет). Порядок блокировок у одного игрока всегда один:
    стопки статистов → стопки уников."""
    stacks = combat_stacks(await list_stacks(session, user_id, camp=camp, for_update=for_update))
    for c in await card_repo.list_stacks(session, user_id, camp=camp, for_update=for_update):
        if c.card_code in ABSOLUTES:  # абсолюты не воюют и не гибнут — пассивка за обладание
            continue
        stacks.append(CombatStack(key=(_KIND_CARD, c.card_code), unit_power=card_power(c.card_code), quantity=c.quantity))
    # Наёмники по контракту воюют в своём лагере, пока контракт действует.
    for contract in await contract_repo.list_active(session, user_id, camp=camp, for_update=for_update):
        stacks.append(
            CombatStack(key=(_KIND_CONTRACT, contract.id), unit_power=extra_unit_power(contract.rank, 0, 0), quantity=contract.quantity)
        )
    # Сила игрока: +1% к мощи армии за ранг (raw-notes «Профиль») — на всех бойцах лагеря.
    multiplier = await strength_power_multiplier(session, user_id) / 100
    if multiplier != 1:
        stacks = [replace(s, unit_power=s.unit_power * multiplier) for s in stacks]
    return stacks


async def apply_losses(session: AsyncSession, user_id: int, camp: str, dead: dict) -> None:
    """Списывает погибших из стопок лагеря — статистов и уников (НЕ коммитит — шаг
    составной операции)."""
    for key, count in dead.items():
        if key[0] == _KIND_CONTRACT:
            await contract_repo.lose(session, key[1], count)
        elif key[0] == _KIND_CARD:
            await card_repo.add_to_stack(session, user_id=user_id, card_code=key[1], camp=camp, quantity=-count)
        else:
            _, rank, stars, training_level, school, school_level = key
            await add_to_stack(
                session, user_id=user_id, camp=camp, rank=rank, stars=stars, training_level=training_level,
                quantity=-count, school=school, school_level=school_level,
            )
