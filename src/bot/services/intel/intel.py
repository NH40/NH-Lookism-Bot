"""Разведка — отчёт о другом игроке и метки (сервис).

Открывается системами развития (`EconomyMods`):
- `scout` (гений хакинга, гений наблюдения): 1 — мощь лагерей цели, 2 — их состав по рангам,
  3 — её билд (родословная, путь, техника, гениальность с уровнями);
- `logs` (гений наблюдения): журнал действий цели — 1 бои, 2 + захваты и бизнес, 3 всё
  (пользователь: «наблюдать, как действуют игроки, читать логи… кто к чему готовится»);
- `marks` (гений наблюдения, путь Сенсорики): метки на игроков и лента их действий.

Скрытность (родословная Куроды, `stealth`) прячет цель от разведки и журналов ниже
3-го уровня — видно только, что она скрыта.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.activity import LOG_ENTRIES_BY_LEVEL, LOG_KINDS_BY_LEVEL, MARK_FEED_ENTRIES
from bot.constant.activity import ACT_BATTLE, ACT_BUSINESS, ACT_CAPTURE, ACT_DEVELOPMENT
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.db.repositories import activity as activity_repo
from bot.db.repositories import build as build_repo
from bot.db.repositories.build import BuildRow
from bot.db.repositories.user import find_by_username, get_by_id
from bot.services.build import get_build
from bot.services.district.army import load_camp

_STEALTH_PIERCE_LEVEL = 3
_ALL_KINDS = (ACT_BATTLE, ACT_CAPTURE, ACT_BUSINESS, ACT_DEVELOPMENT)


class NoIntelError(Exception):
    """У игрока нет ни разведки, ни наблюдения, ни меток."""


class TargetNotFoundError(Exception):
    pass


class UnmarkableError(Exception):
    """Цель под «Призраком» (Безопасность) — её нельзя пометить."""


class MarksFullError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        self.limit = limit


@dataclass(frozen=True, slots=True)
class CampIntel:
    power: int
    quantity: int
    top: list[tuple[str, int]] = field(default_factory=list)  # (подпись стопки, количество) по мощи


@dataclass(frozen=True, slots=True)
class IntelReport:
    target_id: int
    username: str | None
    display_name: str | None
    stealth_hidden: bool
    scout: int
    logs: int
    attack: CampIntel | None = None
    defense: CampIntel | None = None
    build: BuildRow | None = None
    entries: list[tuple[datetime, str]] = field(default_factory=list)
    marked: bool = False
    can_mark: bool = False
    can_sabotage: bool = False  # путь Сенсорики: саботаж помеченного


@dataclass(frozen=True, slots=True)
class IntelAccess:
    scout: int
    logs: int
    marks: int

    @property
    def any(self) -> bool:
        return bool(self.scout or self.logs or self.marks)


async def get_access(session: AsyncSession, user_id: int) -> IntelAccess:
    eco = (await get_build(session, user_id)).eco
    return IntelAccess(scout=eco.scout, logs=eco.logs, marks=eco.marks)


def _stack_label(key) -> str:
    if key[0] == "u":
        return f"уник:{key[1]}"
    if key[0] == "c":
        return "наёмники по контракту"
    _, rank, stars, level, school, school_level = key
    return f"{rank}{'★' * stars}{f' т{level}' if level else ''}{f' {school}{school_level}' if school else ''}"


async def _camp(session: AsyncSession, user_id: int, camp: str, detailed: bool) -> CampIntel:
    stacks = await load_camp(session, user_id, camp, for_update=False)
    power = int(sum(s.unit_power * s.quantity for s in stacks))
    quantity = sum(s.quantity for s in stacks)
    top: list[tuple[str, int]] = []
    if detailed:
        by_label: dict[str, int] = defaultdict(int)
        power_of: dict[str, float] = defaultdict(float)
        for s in stacks:
            label = _stack_label(s.key)
            by_label[label] += s.quantity
            power_of[label] += s.unit_power * s.quantity
        top = sorted(by_label.items(), key=lambda kv: power_of[kv[0]], reverse=True)[:6]
    return CampIntel(power=power, quantity=quantity, top=top)


async def get_report(session: AsyncSession, viewer_id: int, username: str) -> IntelReport:
    access = await get_access(session, viewer_id)
    if not access.any:
        raise NoIntelError
    target = await find_by_username(session, username)
    if target is None or target.id == viewer_id:
        raise TargetNotFoundError
    target_eco = (await get_build(session, target.id)).eco
    hidden = target_eco.stealth and max(access.scout, access.logs) < _STEALTH_PIERCE_LEVEL
    marks = await activity_repo.list_marks(session, viewer_id)
    report = dict(
        target_id=target.id, username=target.username, display_name=target.display_name,
        stealth_hidden=hidden, scout=access.scout, logs=access.logs,
        marked=target.id in marks, can_mark=access.marks > 0,
        can_sabotage=target.id in marks and "sabotage_marked" in (await get_build(session, viewer_id)).flags,
    )
    if hidden:
        return IntelReport(**report)
    if access.scout >= 1:
        report["attack"] = await _camp(session, target.id, CAMP_ATTACK, access.scout >= 2)
        report["defense"] = await _camp(session, target.id, CAMP_DEFENSE, access.scout >= 2)
    if access.scout >= 3:
        report["build"] = await build_repo.get_row(session, target.id)
    if access.logs >= 1:
        report["entries"] = await activity_repo.recent(
            session, target.id, LOG_KINDS_BY_LEVEL[min(access.logs, 3)], LOG_ENTRIES_BY_LEVEL[min(access.logs, 3)]
        )
    return IntelReport(**report)


async def toggle_mark(session: AsyncSession, viewer_id: int, target_id: int) -> bool:
    """Поставить/снять метку. → True — метка теперь стоит. Коммитит."""
    access = await get_access(session, viewer_id)
    marks = await activity_repo.list_marks(session, viewer_id)
    if target_id in marks:
        await activity_repo.remove_mark(session, viewer_id, target_id)
        await session.commit()
        return False
    if len(marks) >= access.marks:
        raise MarksFullError(access.marks)
    target_pos = (await get_build(session, target_id)).positions
    if target_pos is not None and target_pos.get("unmarkable"):
        raise UnmarkableError
    await activity_repo.add_mark(session, viewer_id, target_id)
    await session.commit()
    return True


@dataclass(frozen=True, slots=True)
class MarkFeed:
    target_id: int
    username: str | None
    display_name: str | None
    hidden: bool
    entries: list[tuple[datetime, str]]


async def get_marks_feed(session: AsyncSession, viewer_id: int) -> tuple[int, list[MarkFeed]]:
    """(лимит меток, лента по каждому помеченному)."""
    access = await get_access(session, viewer_id)
    feeds = []
    for target_id in await activity_repo.list_marks(session, viewer_id):
        target = await get_by_id(session, target_id)
        if target is None:
            continue
        hidden = (await get_build(session, target_id)).eco.stealth and max(access.scout, access.logs) < _STEALTH_PIERCE_LEVEL
        entries = [] if hidden else await activity_repo.recent(session, target_id, _ALL_KINDS, MARK_FEED_ENTRIES)
        feeds.append(MarkFeed(target_id, target.username, target.display_name, hidden, entries))
    return access.marks, feeds
