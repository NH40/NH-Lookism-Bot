"""Родословная (сервис). Дизайн — `docs/design/development_systems.md`.

Пользователь 2026-10-02: 10 родословных; игрок **один раз выбирает сам** (при регистрации —
AskUserQuestion), после этого сменить нельзя — **только донатом** (появится с магазином).
Пробуждается **каплями крови** (боссы на карте, позже — пробуждение); у каждой родословной
своя ветка из 10 уровней (`config/bloodline`), «каждый уровень — почти новая механика».
Уровень 1 — сразу при выборе. Удаление банды родословную, уровень и капли не трогает.

Бафы уровней собирает `services/build`. Здесь — то, что меняет данные игрока, а не числа
боя: **пол характеристик** Ким Гапрена (`stat_floor`, характеристики поднимаются до него и
не падают ниже после сброса) и **техника Преодоления без учителя** (`grant_overcome`).
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_DEV_LEVEL

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.bloodline import BLOODLINE_START_LEVEL, LEVELS, bloodline_level_cost
from bot.config.development import MAX_LEVEL
from bot.constant.activity import ACT_DEVELOPMENT
from bot.constant.bloodline import BLOODLINES
from bot.constant.unique_technique import TECH_OVERCOME
from bot.db.repositories import bloodline as bloodline_repo
from bot.db.repositories import donate as donate_repo
from bot.services.activity import log as log_activity
from bot.services.build import level_effect
from bot.texts.activity import LOG_BLOODLINE_LEVEL


class UnknownBloodlineError(Exception):
    pass


class BloodlineAlreadyChosenError(Exception):
    pass


class NoBloodlineError(Exception):
    pass


class BloodlineMaxLevelError(Exception):
    pass


class NotEnoughBloodError(Exception):
    def __init__(self, cost: int, have: int) -> None:
        super().__init__(cost, have)
        self.cost, self.have = cost, have


@dataclass(frozen=True, slots=True)
class BloodlineState:
    code: str | None  # None — ещё не выбрана
    level: int
    blood_drops: int

    @property
    def next_cost(self) -> int | None:
        if self.code is None or self.level >= MAX_LEVEL:
            return None
        return bloodline_level_cost(self.level + 1)


async def get_state(session: AsyncSession, user_id: int) -> BloodlineState | None:
    row = await bloodline_repo.get_state(session, user_id)
    return BloodlineState(*row) if row else None


async def apply_effects(session: AsyncSession, user_id: int) -> None:
    """Данные игрока, которые меняет уровень родословной: пол характеристик и техника
    Преодоления. Идемпотентно — вызывается после выбора, повышения уровня и удаления банды.
    НЕ коммитит."""
    state = await get_state(session, user_id)
    if state is None or state.code is None:
        return
    pairs = [(state.code, state.level)]
    body = await donate_repo.body_state(session, user_id)
    if body and body[0] and body[3]:  # вторая родословная второго тела
        pairs.append((body[3], body[4]))
    for code, level in pairs:
        effect = level_effect(LEVELS, code, level)
        if effect.eco.stat_floor:
            await bloodline_repo.raise_stats_to(session, user_id, effect.eco.stat_floor)
        if effect.special.get("grant_overcome"):
            # Отложенный импорт: домен техник использует журнал и квесты, родословная — его.
            from bot.services.unique_technique import grant

            await grant(session, user_id, TECH_OVERCOME)


async def choose(session: AsyncSession, user_id: int, code: str) -> None:
    if code not in BLOODLINES:
        raise UnknownBloodlineError(code)
    if not await bloodline_repo.choose(session, user_id, code):
        raise BloodlineAlreadyChosenError
    await bloodline_repo.set_level_if_zero(session, user_id, BLOODLINE_START_LEVEL)
    await apply_effects(session, user_id)
    await session.commit()


class NoSecondBodyError(Exception):
    pass


async def choose2(session: AsyncSession, user_id: int, code: str) -> None:
    """Вторая родословная (донат «второе тело», пользователь 2026-10-08): любая, кроме первой,
    выбирается один раз; бафы обеих действуют сразу, уровни — свои, капли крови общие. Коммитит."""
    if code not in BLOODLINES:
        raise UnknownBloodlineError(code)
    body = await donate_repo.body_state(session, user_id)
    if not body or not body[0]:
        raise NoSecondBodyError
    if not await donate_repo.choose_bloodline2(session, user_id, code, BLOODLINE_START_LEVEL):
        raise BloodlineAlreadyChosenError
    await apply_effects(session, user_id)
    await session.commit()


async def level_up2(session: AsyncSession, user_id: int) -> int:
    """+1 уровень второй родословной за капли крови. Коммитит. → новый уровень."""
    body = await donate_repo.body_state(session, user_id)
    if not body or not body[0] or not body[3]:
        raise NoBloodlineError
    level, drops = body[4], body[5]
    if level >= MAX_LEVEL:
        raise BloodlineMaxLevelError
    cost = bloodline_level_cost(level + 1)
    if not await donate_repo.level_up_bloodline2(session, user_id, level, cost):
        raise NotEnoughBloodError(cost, drops)
    await apply_effects(session, user_id)
    await quest_event(session, user_id, TASK_DEV_LEVEL)
    await session.commit()
    return level + 1


async def level_up(session: AsyncSession, user_id: int) -> int:
    """+1 уровень за капли крови. Коммитит. → новый уровень."""
    state = await get_state(session, user_id)
    if state is None or state.code is None:
        raise NoBloodlineError
    if state.level >= MAX_LEVEL:
        raise BloodlineMaxLevelError
    cost = bloodline_level_cost(state.level + 1)
    if not await bloodline_repo.level_up(session, user_id, state.level, cost):
        raise NotEnoughBloodError(cost, state.blood_drops)
    await apply_effects(session, user_id)
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_BLOODLINE_LEVEL.format(level=state.level + 1))
    await quest_event(session, user_id, TASK_DEV_LEVEL)
    await session.commit()
    return state.level + 1
