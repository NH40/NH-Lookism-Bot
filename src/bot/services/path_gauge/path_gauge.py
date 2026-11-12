"""Шкалы путей: рост и эффект (сервис).

Эффект шкалы (`gauge_effect`) собирает `services/build` вместе с остальными бафами. Рост — здесь: после
боя (`after_battle`, из единой точки `services/absolute/battle.after_battle`) и от действий вне боя
(`add_for_paths`: заработок, разведка, саботаж, уровни техник). Все функции НЕ коммитят — это шаги
операций вызывающего кода (правило 10); запись — один атомарный UPDATE с потолком по уровню пути.
"""
from __future__ import annotations

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.bloodline import LEVELS as BLOODLINE_LEVELS
from bot.config.path_gauge import (
    GAUGE_CAP_PER_LEVEL,
    GAUGE_MAX,
    GAUGE_MAX_PER_BATTLE,
    GAUGE_PVP_WEIGHT,
    PATH_GAUGES,
)
from bot.constant.unique_path import (
    COPYING_PATHS,
    PATH_ABSORPTION,
    PATH_ADAPTATION,
    PATH_COPY,
    PATH_DESPAIR,
    PATH_EVASION,
    PATH_FORESIGHT,
    PATH_INFINITE,
    PATH_OVERCOME,
    PATH_SURE_HIT,
)
from bot.db.models.development import UserPath
from bot.db.repositories import build as build_repo
from bot.services.build.mods import NO_ECO, EconomyMods
from bot.services.combat.mods import NO_MODS, CombatMods


def gauge_effect(code: str | None, value: float, power: float = 1.0) -> tuple[CombatMods, EconomyMods, dict]:
    """Бафы шкалы пути при значении `value` (без учёта потолка — он уже в БД). `power` — усиление
    шкалы (родословная Александровых для Адаптации). → (бой, экономика, особое)."""
    spec = PATH_GAUGES.get(code or "")
    if spec is None or value <= 0:
        return NO_MODS, NO_ECO, {}
    k = min(1.0, value / GAUGE_MAX) * power
    combat = CombatMods.of(spec.combat).scale(k) if spec.combat else NO_MODS
    eco = NO_ECO
    if spec.eco:
        eco = EconomyMods.of({key: type(v)(v * k) if isinstance(v, int) else v * k for key, v in spec.eco.items()})
    for threshold, tier in spec.tiers:
        if value >= threshold:
            eco = eco + EconomyMods.of(tier)
    return combat, eco, {key: v * k for key, v in spec.special.items()}


def technique_gauge_effect(code: str | None, value: float) -> CombatMods:
    """Бафы шкалы техники (`config/unique_technique.TECH_GAUGES`) при значении `value`."""
    from bot.config.unique_technique import TECH_GAUGES

    spec = TECH_GAUGES.get(code or "")
    if not spec or value <= 0:
        return NO_MODS
    return CombatMods.of(spec).scale(min(1.0, value / GAUGE_MAX))


async def add(session: AsyncSession, user_id: int, code: str, amount: float) -> None:
    """+к шкале пути, не выше потолка его уровня. НЕ коммитит."""
    if amount <= 0 or code not in PATH_GAUGES:
        return
    await session.execute(
        update(UserPath)
        .where(UserPath.user_id == user_id, UserPath.code == code)
        .values(gauge=func.least(UserPath.gauge + amount, UserPath.level * GAUGE_CAP_PER_LEVEL))
    )


async def add_for_paths(session: AsyncSession, user_id: int, codes: frozenset[str] | set[str], amount: float) -> None:
    """Прибавка к шкале, если один из активных путей игрока — из `codes`. НЕ коммитит."""
    row = await build_repo.get_row(session, user_id)
    if row is None:
        return
    for code in {row.path, row.path2} & set(codes):
        await add(session, user_id, code, amount)


def _speed(row, code: str) -> float:
    """Ускорение шкалы от родословной: Джинен — копирование, Александровы — адаптация."""
    key = "copy_gauge_speed" if code in COPYING_PATHS else "adaptation_gauge_speed" if code == PATH_ADAPTATION else None
    if key is None:
        return 1.0
    from bot.services.build import level_effect

    bonus = 0.0
    for bloodline, level in ((row.bloodline, row.bloodline_level), (row.bloodline2, row.bloodline2_level)):
        bonus += level_effect(BLOODLINE_LEVELS, bloodline, level).special.get(key, 0.0)
    return 1 + bonus


def _battle_gain(code: str, side, foe, won: bool) -> float:
    """Сколько шкалы даёт бой (до веса PvP и потолка за бой)."""
    power, quantity = side.initial_power or 1, side.initial_quantity or 1
    if code == PATH_OVERCOME:  # чем сильнее противник, тем больше
        return 1 + min(3.0, max(0.0, foe.initial_power / power - 1))
    if code == PATH_DESPAIR:  # только за победы; больше убил — больше шкалы
        return (1 + min(2.0, 2 * side.kills / quantity)) if won else 0.0
    if code == PATH_ABSORPTION:
        return min(3.0, 3 * side.absorbed / power)
    if code == PATH_ADAPTATION:
        return 0.5 + min(3.0, 3 * side.taken / power)
    if code == PATH_EVASION:
        return min(3.0, 3 * side.dodged / quantity)
    if code == PATH_FORESIGHT:
        return 1.0
    if code == PATH_SURE_HIT:
        return 0.5 + (1.0 if won else 0.0)
    if code in (PATH_COPY, PATH_INFINITE):
        return 1.0
    return 0.0


async def after_battle(session: AsyncSession, user_id: int, side, foe, won: bool, pvp: bool) -> None:
    """Шкалы активных путей бойца после боя (`side`/`foe` — `SideOutcome`). НЕ коммитит."""
    if not side.initial_quantity:
        return
    row = await build_repo.get_row(session, user_id)
    if row is None:
        return
    for code in filter(None, (row.path, row.path2)):
        gain = _battle_gain(code, side, foe, won) * _speed(row, code) * (GAUGE_PVP_WEIGHT if pvp else 1.0)
        await add(session, user_id, code, min(GAUGE_MAX_PER_BATTLE, gain))
    # Шкала CQC: за убитых (больше убил — больше шкалы), победа добавляет сверху.
    from bot.config.unique_technique import TECH_GAUGES
    from bot.db.repositories import unique_technique as tech_repo

    if row.technique in TECH_GAUGES:
        gain = (min(2.5, 2.5 * side.kills / side.initial_quantity) + (0.5 if won else 0.0)) * (GAUGE_PVP_WEIGHT if pvp else 1.0)
        if gain > 0:
            await tech_repo.add_gauge(session, user_id, row.technique, min(GAUGE_MAX_PER_BATTLE, gain), GAUGE_CAP_PER_LEVEL)
