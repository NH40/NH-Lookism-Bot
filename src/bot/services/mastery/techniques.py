"""Техники мастерства (сервис, 2026-11-19): изучение по ступеням дерева, цена — фрагменты техник."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.mastery.techniques import MASTERY_TECH_TIERS, MASTERY_TREES, tech_by_code, tier_cost
from bot.constant.resource import RES_TECHNIQUE_FRAGMENTS
from bot.db.models.development import MasteryTechnique
from bot.db.models.user import User

_COLUMNS = {"strength": User.mastery_strength, "speed": User.mastery_speed, "endurance": User.mastery_endurance, "technique": User.mastery_technique}


class MasteryTechError(Exception):
    def __init__(self, code: str, value: int = 0) -> None:
        super().__init__(code)
        self.code, self.value = code, value


@dataclass(frozen=True, slots=True)
class TreeView:
    mastery: str
    unlocked: bool
    learned: dict[int, str]  # ступень → код
    next_tier: int | None
    cost: int | None


async def view(session: AsyncSession, user_id: int) -> tuple[list[TreeView], int]:
    """Деревья всех мастерств и фрагменты техник игрока."""
    from bot.services.resource import balance

    points = (await session.execute(select(*_COLUMNS.values()).where(User.id == user_id))).one()
    rows = (await session.execute(select(MasteryTechnique.mastery, MasteryTechnique.tier, MasteryTechnique.code).where(MasteryTechnique.user_id == user_id))).all()
    learned: dict[str, dict[int, str]] = {}
    for m, tier, code in rows:
        learned.setdefault(m, {})[int(tier)] = code
    out = []
    for (m, _), pts in zip(_COLUMNS.items(), points):
        own = learned.get(m, {})
        nxt = len(own) + 1 if len(own) < MASTERY_TECH_TIERS else None
        out.append(TreeView(m, int(pts or 0) >= 1, own, nxt, tier_cost(nxt) if nxt else None))
    return out, await balance(session, user_id, RES_TECHNIQUE_FRAGMENTS)


async def learn(session: AsyncSession, user_id: int, mastery: str, code: str) -> str:
    """Изучить технику следующей ступени. → название. Коммитит."""
    from bot.services.resource import balance, spend

    if mastery not in MASTERY_TREES:
        raise MasteryTechError("bad")
    found = tech_by_code(mastery, code)
    if found is None:
        raise MasteryTechError("bad")
    tier, tech = found
    trees, _ = await view(session, user_id)
    tree = next(t for t in trees if t.mastery == mastery)
    if not tree.unlocked:
        raise MasteryTechError("locked")
    if tree.next_tier != tier:
        raise MasteryTechError("tier")
    cost = tier_cost(tier)
    if not await spend(session, user_id, RES_TECHNIQUE_FRAGMENTS, cost):
        have = await balance(session, user_id, RES_TECHNIQUE_FRAGMENTS)
        await session.rollback()
        raise MasteryTechError("fragments", cost - have)
    session.add(MasteryTechnique(user_id=user_id, mastery=mastery, tier=tier, code=code))
    await session.commit()
    return tech.name


ERRORS = {
    "bad": "Нет такой техники.",
    "locked": "Сначала пройди первый этап «Преодоления стены» и вложи очко в это мастерство.",
    "tier": "Сначала изучи технику предыдущей ступени.",
    "fragments": "Не хватает фрагментов техник: ещё {value}.",
}
