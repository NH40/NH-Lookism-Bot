"""Перки игрока в онлайн-бою (2026-11-19): из его активных систем развития (`config/arena/sources`)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.arena.sources import TIER_LEVELS


def _tiers(prefix: str, code: str | None, level: int) -> list[str]:
    return [f"{prefix}:{code}:{t + 1}" for t, need in enumerate(TIER_LEVELS) if code and level >= need]


async def perks_for(session: AsyncSession, user_id: int) -> list[str]:
    """Коды перков: базовые всем + техника, пути (оба тела), родословные, активные абсолюты, позиции банды,
    изученные техники мастерства. Только те, что есть в реестре."""
    from sqlalchemy import select

    from bot.config.arena.perks import BASE_PERKS
    from bot.db.models.development import MasteryTechnique
    from bot.db.repositories import build as build_repo
    from bot.db.repositories.card.card import list_positions
    from bot.services.absolute import active as active_absolutes
    from bot.services.arena.arena import PERK_REGISTRY

    row = await build_repo.get_row(session, user_id)
    codes = list(BASE_PERKS)
    if row is not None:
        codes += _tiers("tech", row.technique, row.technique_level)
        codes += _tiers("path", row.path, row.path_level) + _tiers("path", row.path2, row.path2_level)
        codes += _tiers("blood", row.bloodline, row.bloodline_level) + _tiers("blood", row.bloodline2, row.bloodline2_level)
    codes += [f"abs:{a}" for a in sorted(await active_absolutes(session, user_id))]
    codes += [f"pos:{p.position}" for p in await list_positions(session, user_id) if p.card_code]
    learned = (await session.execute(select(MasteryTechnique.code).where(MasteryTechnique.user_id == user_id))).scalars().all()
    codes += [f"mt:{c}" for c in learned]
    seen: set[str] = set()
    return [c for c in codes if c in PERK_REGISTRY and not (c in seen or seen.add(c))]
