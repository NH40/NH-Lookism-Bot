"""Хансу «Фокус тренировки» (сервис, пользователь 2026-11-28).

Игрок отмечает отряды — лагерь + ранг + школа (уровень и звёзды меняются каждую тренировку, по ним выбор
слетал бы) — и весь обычный охват тренировки статистов (`EXTRA_TRAINING_COVERAGE_PERCENT` армии) достаётся им.
Бойцов в фокусе меньше квоты — остаток идёт остальной армии, так что с фокусом не хуже, чем без него. Боец,
перешедший на следующий ранг, из фокуса выходит. Слоты — `EconomyMods.focus_slots` (1/2/3/5 на 1/4/7/10-м уровне
родословной), берутся из обычного билда и в автотренировке Ямадзаки тоже — фокус выбор, а не бонус.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.characteristic import RANK_INDEX
from bot.constant.extra import CAMPS
from bot.db.models.user import User
from bot.db.repositories.extra import list_stacks

FocusKey = tuple[str, str, str]  # (лагерь, ранг, школа или "")


class FocusUnavailableError(Exception):
    """Фокус тренировки — только у родословной Хансу."""


class FocusSlotsFullError(Exception):
    def __init__(self, slots: int) -> None:
        super().__init__(slots)
        self.slots = slots


def focus_key(camp: str, rank: str, school: str | None) -> FocusKey:
    return camp, rank, school or ""


async def _slots(session: AsyncSession, user_id: int) -> int:
    from bot.services.build import get_build

    return int((await get_build(session, user_id)).eco.focus_slots)


async def active_focus(session: AsyncSession, user_id: int) -> frozenset[FocusKey]:
    """Отряды в фокусе с учётом слотов (уровень родословной упал — лишние не действуют)."""
    slots = await _slots(session, user_id)
    if slots <= 0:
        return frozenset()
    saved = await session.scalar(select(User.training_focus).where(User.id == user_id)) or []
    return frozenset(focus_key(*item) for item in saved[:slots] if isinstance(item, list) and len(item) == 3)


@dataclass(frozen=True, slots=True)
class FocusRow:
    camp: str
    rank: str
    school: str
    quantity: int
    focused: bool


@dataclass(frozen=True, slots=True)
class FocusView:
    slots: int
    used: int
    rows: list[FocusRow]


async def focus_view(session: AsyncSession, user_id: int) -> FocusView:
    """Экран фокуса: строка на отряд (лагерь+ранг+школа), сильные ранги первыми."""
    slots = await _slots(session, user_id)
    if slots <= 0:
        raise FocusUnavailableError
    focus = await active_focus(session, user_id)
    totals: dict[FocusKey, int] = {}
    for s in await list_stacks(session, user_id):
        if s.quantity > 0:
            key = focus_key(s.camp, s.rank, s.school)
            totals[key] = totals.get(key, 0) + s.quantity
    rows = [FocusRow(camp=k[0], rank=k[1], school=k[2], quantity=q, focused=k in focus) for k, q in totals.items()]
    camp_order = {c: i for i, c in enumerate(CAMPS)}
    rows.sort(key=lambda r: (not r.focused, -RANK_INDEX.get(r.rank, 0), camp_order.get(r.camp, 9), r.school))
    return FocusView(slots=slots, used=len(focus), rows=rows)


async def toggle_focus(session: AsyncSession, user_id: int, camp: str, rank: str, school: str) -> bool:
    """Добавить/убрать отряд из фокуса. Под блокировкой строки игрока (правило 1). Коммитит. → в фокусе ли теперь."""
    if camp not in CAMPS or rank not in RANK_INDEX:
        raise FocusUnavailableError
    slots = await _slots(session, user_id)
    if slots <= 0:
        raise FocusUnavailableError
    saved = await session.scalar(select(User.training_focus).where(User.id == user_id).with_for_update()) or []
    current = [focus_key(*item) for item in saved[:slots] if isinstance(item, list) and len(item) == 3]
    key = focus_key(camp, rank, school)
    if key in current:
        current.remove(key)
        focused = False
    else:
        if len(current) >= slots:
            await session.rollback()
            raise FocusSlotsFullError(slots)
        current.append(key)
        focused = True
    await session.execute(update(User).where(User.id == user_id).values(training_focus=[list(k) for k in current]))
    await session.commit()
    return focused
