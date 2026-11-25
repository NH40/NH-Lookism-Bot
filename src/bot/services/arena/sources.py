"""Перки игрока в онлайн-бою (2026-11-19): из его активных систем развития (`config/arena/sources`)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.arena.branches import perk_base
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
        # пути и родословные — приёмы ветвей v3: 2–3 на ветку, сила от уровня (2026-11-24)
        from bot.config.arena.branches import branch_codes
        from bot.config.path_gauge import COPY_PERK_GAUGE
        from bot.constant.unique_path import PATH_COPY

        for path, level, gauge in ((row.path, row.path_level, row.path_gauge), (row.path2, row.path2_level, row.path2_gauge)):
            got = branch_codes("path", path, level)
            if path == PATH_COPY and gauge < COPY_PERK_GAUGE:  # «Копию» открывает шкала копирования
                got = [c for c in got if not c.startswith(f"path:{PATH_COPY}:1@")]
            codes += got
        codes += branch_codes("blood", row.bloodline, row.bloodline_level) + branch_codes("blood", row.bloodline2, row.bloodline2_level)
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
    return _cap([c for c in out if perk_base(c) not in off])


def _cap(enabled: list[str]) -> list[str]:
    """Набор на бой — не больше `ARENA_LOADOUT_MAX`: лишние (игрок ещё не настраивал) — отсекаются по силе для
    автобоя (`perk_value`), порядок показа сохраняется."""
    from bot.config.arena import ARENA_LOADOUT_MAX
    from bot.services.arena.arena import PERK_REGISTRY, perk_value

    if len(enabled) <= ARENA_LOADOUT_MAX:
        return enabled
    keep = set(sorted(enabled, key=lambda c: (-perk_value(PERK_REGISTRY[c]), c))[:ARENA_LOADOUT_MAX])
    return [c for c in enabled if c in keep]


class LoadoutFullError(Exception):
    """В наборе уже `ARENA_LOADOUT_MAX` перков — сначала выключи другой."""


async def loadout(session: AsyncSession, user_id: int) -> tuple[list[str], list[str], bool]:
    """Экран набора: (все доступные перки, те, что в наборе на бой, «начинать на автобое»)."""
    from sqlalchemy import select

    from bot.db.models.user import User

    row = (await session.execute(select(User.arena_perks_off, User.arena_auto_default).where(User.id == user_id))).one()
    every = await perks_for(session, user_id, include_off=True)
    off = set(row[0] or [])
    return every, _cap([c for c in every if perk_base(c) not in off]), bool(row[1])


async def toggle_loadout(session: AsyncSession, user_id: int, code: str) -> None:
    """Перк в набор / из набора. Первое изменение фиксирует набор (то, что не влезло в 8, — выключается), девятый
    не включить. Коммитит."""
    from bot.config.arena import ARENA_LOADOUT_MAX

    every, chosen, _ = await loadout(session, user_id)
    code = next((c for c in every if perk_base(c) == perk_base(code)), None)  # уровень ветки мог вырасти с экрана
    if code is None:
        return
    chosen = [c for c in chosen if c != code] if code in chosen else chosen + [code]
    if len(chosen) > ARENA_LOADOUT_MAX:
        raise LoadoutFullError
    await _save_off(session, user_id, every, chosen)
    await session.commit()


async def _save_off(session: AsyncSession, user_id: int, every: list[str], chosen: list[str]) -> None:
    """Записать набор как список выключенных (без уровня: прокачка ветки набор не сбивает). Выключенные перки,
    которых сейчас нет среди доступных (абсолют под блоком Ариана), остаются выключенными — иначе по концу блока
    перк сам вернулся бы в набор и вытеснил выбранный игроком (2026-11-25). НЕ коммитит."""
    from sqlalchemy import select, update

    from bot.db.models.user import User

    old = await session.scalar(select(User.arena_perks_off).where(User.id == user_id)) or []
    bases = {perk_base(c) for c in every}
    off = [perk_base(c) for c in every if c not in chosen] + [b for b in old if b not in bases]
    await session.execute(update(User).where(User.id == user_id).values(arena_perks_off=list(dict.fromkeys(off))))


async def freeze_without_absolutes(session: AsyncSession, user_id: int) -> None:
    """Ариан гасит абсолюты цели (пользователь 2026-11-25): набор не перестраивается. Перки абсолютов выключаются,
    их слоты остаются пустыми (бьётся 7 из 8, пока сам не поставит другой), остальное — как было. По концу блока
    абсолют появится выключенным — включит сам. Вызывать ДО записи блока. НЕ коммитит."""
    from bot.services.absolute import owned

    if not await owned(session, user_id):
        return  # абсолютов нет — набору нечего терять
    every, chosen, _ = await loadout(session, user_id)
    await _save_off(session, user_id, every, [c for c in chosen if not c.startswith("abs:")])


async def set_auto_default(session: AsyncSession, user_id: int, on: bool) -> None:
    from sqlalchemy import update

    from bot.db.models.user import User

    await session.execute(update(User).where(User.id == user_id).values(arena_auto_default=bool(on)))
    await session.commit()


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
    regen += 1 if int(endurance or 0) >= cfg.ARENA_END_REGEN_RANK else 0  # Выносливость (2026-11-23)
    cap = cfg.ARENA_ENERGY_MAX + int(mastery or 0)
    return min(start, cap), regen, cap
