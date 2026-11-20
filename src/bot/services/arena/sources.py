"""Перки игрока в онлайн-бою (2026-11-19): из его активных систем развития (`config/arena/sources`)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.arena.sources import TIER_LEVELS


def _tiers(prefix: str, code: str | None, level: int) -> list[str]:
    return [f"{prefix}:{code}:{t + 1}" for t, need in enumerate(TIER_LEVELS) if code and level >= need]


async def perks_for(session: AsyncSession, user_id: int, *, include_off: bool = False) -> list[str]:
    """Коды перков: базовые всем + техника, пути (оба тела), родословные, активные абсолюты, позиции банды,
    изученные техники мастерства. Только те, что есть в реестре. Отключённые игроком (`users.arena_perks_off`)
    в бой не попадают — автоатака их не жмёт (2026-11-20); `include_off` — для экрана настройки."""
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
    out = [c for c in codes if c in PERK_REGISTRY and not (c in seen or seen.add(c))]
    if include_off:
        return out
    from bot.db.models.user import User

    off = set(await session.scalar(select(User.arena_perks_off).where(User.id == user_id)) or [])
    return [c for c in out if c not in off]


async def energy_for(session: AsyncSession, user_id: int) -> tuple[int, int, int]:
    """(запас на старте, прирост за раунд, потолок) — энергия из выносливости, её мастерства и Ямадзаки."""
    from sqlalchemy import select

    from bot.config import arena as cfg
    from bot.constant.bloodline import BLOODLINE_YAMAZAKI
    from bot.db.models.user import User

    row = (await session.execute(select(
        User.stat_endurance, User.mastery_endurance, User.bloodline, User.bloodline_level, User.bloodline2, User.bloodline2_level,
    ).where(User.id == user_id))).one_or_none()
    if row is None:
        return cfg.ARENA_ENERGY_START, cfg.ARENA_ENERGY_REGEN, cfg.ARENA_ENERGY_MAX
    endurance, mastery, b1, l1, b2, l2 = row
    yama = max(l1 if b1 == BLOODLINE_YAMAZAKI else 0, l2 if b2 == BLOODLINE_YAMAZAKI else 0)
    start = cfg.ARENA_ENERGY_START + int(endurance or 0) // cfg.ARENA_ENERGY_RANKS_PER_START + (2 if yama >= cfg.ARENA_YAMAZAKI_START_LEVEL else 0)
    regen = cfg.ARENA_ENERGY_REGEN + (1 if (mastery or 0) >= cfg.ARENA_ENERGY_MASTERY_REGEN_TIER else 0) + (1 if yama >= cfg.ARENA_YAMAZAKI_REGEN_LEVEL else 0)
    cap = cfg.ARENA_ENERGY_MAX + int(mastery or 0)
    return min(start, cap), regen, cap
