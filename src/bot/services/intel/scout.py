"""Разведка — отдельный этап (сервис, пользователь 2026-10-16).

Кнопка «Разведать» по игроку, без КД. Что попадёт в отчёт — уровни полей разведки банды
(навыки позиции Разведки и др., `PositionEffects.intel`) и гениальности/пути разведки
(`EconomyMods.scout/logs`, старые уровни 1–3 считаются уровнем 3). Против — уровни сокрытия
цели (`PositionEffects.hide`): разведка выше — точное значение, равна — вилка, ниже — «скрыто».
«Дезинформация» цели искажает числа (сквозь неё видит «Глаз бога»), «Всевидящий» превращает
вилку в точное значение. Отчёт — снимок, хранится до следующей разведки той же цели.

Реакции Безопасности цели: «Двойной агент» — цели сообщается, кто разведал; «Тревога» —
что её разведали; «Ответный удар» — разведчик теряет долю статистов младшего ранга.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import battle_cooldown
from bot.config.card import CARD_BY_CODE
from bot.config.position_skill import SKILLS
from bot.constant.activity import ACT_BATTLE
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.constant.position_skill import (
    F_ATTACK_POWER,
    F_BATTLES,
    F_BLOODLINE,
    F_BUSINESS,
    F_CHALLENGES,
    F_CLAN,
    F_COOLDOWNS,
    F_DEFENSE_POWER,
    F_EMPTY_SLOTS,
    F_FORECAST,
    F_GENIUS,
    F_HEADCOUNT,
    F_LINEUP,
    F_PATH,
    F_POTIONS,
    F_RANKS,
    F_SKILLS,
    F_TECHNIQUE,
    F_TOP_SQUADS,
    F_WALLET,
    SEEN_EXACT,
    SEEN_HIDDEN,
    SEEN_RANGE,
)
from bot.db.repositories import activity as activity_repo
from bot.db.repositories import build as build_repo
from bot.db.repositories import business as business_repo
from bot.db.repositories import card as card_repo
from bot.db.repositories import clan as clan_repo
from bot.db.repositories import potion as potion_repo
from bot.db.repositories import scout as scout_repo
from bot.db.repositories.user import find_by_username, get_by_id
from bot.services.build import get_build
from bot.services.district.army import load_camp
from bot.services.position_skill.position_skill import NO_EFFECTS

# Старые уровни разведки систем развития (гений хакинга/наблюдения, путь Сенсорики) → поля.
_LEGACY_LEVEL = 3
_LEGACY_SCOUT = {1: (F_ATTACK_POWER, F_DEFENSE_POWER), 2: (F_HEADCOUNT, F_TOP_SQUADS, F_RANKS),
                 3: (F_BLOODLINE, F_PATH, F_TECHNIQUE, F_GENIUS)}
_RANGE_SPREAD = 0.15
REPORTS_SHOWN = 10


class NoScoutError(Exception):
    """Ни разведчика на позиции, ни разведки от систем развития."""


class ScoutTargetError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ScoutResult:
    target_id: int
    target_label: str
    created_at: datetime
    payload: dict
    notify_target: str | None = None  # "double_agent" (знает, кто) / "alarm" (знает, что разведали)
    trap_lost: int = 0  # «Ответный удар»: сколько статистов потерял разведчик


def _levels(build) -> dict[str, int]:
    positions = build.positions or NO_EFFECTS
    levels = dict(positions.intel)
    for step, fields in _LEGACY_SCOUT.items():
        if build.eco.scout >= step:
            for f in fields:
                levels[f] = max(levels.get(f, 0), _LEGACY_LEVEL)
    if build.eco.logs:
        levels[F_BATTLES] = max(levels.get(F_BATTLES, 0), _LEGACY_LEVEL)
    if build.eco.foresight:
        levels[F_FORECAST] = max(levels.get(F_FORECAST, 0), _LEGACY_LEVEL)
    return levels


def _fake(viewer_id: int, target_id: int, field: str, spread: float) -> float:
    """Детерминированное искажение «Дезинформации» (одно и то же у пары в течение суток)."""
    day = datetime.now(timezone.utc).date().isoformat()
    h = int(hashlib.md5(f"{viewer_id}:{target_id}:{field}:{day}".encode()).hexdigest()[:6], 16) / 0xFFFFFF
    return 1 + (h * 2 - 1) * min(0.5, spread)


async def _values(session: AsyncSession, redis: Redis, target_id: int, fields: set[str]) -> dict:
    """Настоящие значения нужных полей цели (JSON-совместимые, без подписей)."""
    out: dict = {}
    camps = {}
    if fields & {F_HEADCOUNT, F_ATTACK_POWER, F_DEFENSE_POWER, F_RANKS, F_TOP_SQUADS}:
        camps = {c: await load_camp(session, target_id, c, for_update=False) for c in (CAMP_ATTACK, CAMP_DEFENSE)}
    if F_HEADCOUNT in fields:
        out[F_HEADCOUNT] = sum(s.quantity for st in camps.values() for s in st)
    if F_ATTACK_POWER in fields:
        out[F_ATTACK_POWER] = int(sum(s.unit_power * s.quantity for s in camps[CAMP_ATTACK]))
    if F_DEFENSE_POWER in fields:
        out[F_DEFENSE_POWER] = int(sum(s.unit_power * s.quantity for s in camps[CAMP_DEFENSE]))
    if F_RANKS in fields or F_TOP_SQUADS in fields:
        by_rank: dict[str, int] = defaultdict(int)
        squads: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
        for st in camps.values():
            for s in st:
                key = s.key
                rank = key[1] if isinstance(key, tuple) and key[0] not in ("u", "c") else ("уник" if key[0] == "u" else "контракт")
                by_rank[rank] += s.quantity
                label = rank if key[0] not in ("u",) else f"уник {CARD_BY_CODE[key[1]].name if key[1] in CARD_BY_CODE else key[1]}"
                squads[label][0] += s.quantity
                squads[label][1] += s.unit_power * s.quantity
        out[F_RANKS] = sorted(by_rank.items(), key=lambda kv: -kv[1])[:8]
        out[F_TOP_SQUADS] = [[k, int(v[0])] for k, v in sorted(squads.items(), key=lambda kv: -kv[1][1])[:3]]
    if fields & {F_LINEUP, F_EMPTY_SLOTS, F_SKILLS}:
        lineup = {p.position: p.card_code for p in await card_repo.list_positions(session, target_id)}
        out[F_LINEUP] = [[pos, CARD_BY_CODE[c].name] for pos, c in lineup.items() if c in CARD_BY_CODE]
        from bot.constant.card import POSITIONS

        out[F_EMPTY_SLOTS] = [p for p in POSITIONS if p not in lineup]
        if F_SKILLS in fields:
            positions = (await get_build(session, target_id)).positions or NO_EFFECTS
            out[F_SKILLS] = [[s.position, s.skill.name] for s in positions.skills if (s.position, s.skill.code) in SKILLS]
    if fields & {F_BLOODLINE, F_PATH, F_TECHNIQUE, F_GENIUS}:
        row = await build_repo.get_row(session, target_id)
        if row is not None:
            out[F_BLOODLINE] = [row.bloodline, row.bloodline_level]
            out[F_PATH] = [row.path, row.path_level]
            out[F_TECHNIQUE] = [row.technique, row.technique_level]
            out[F_GENIUS] = [row.genius, row.genius_level]
    if F_POTIONS in fields:
        now = datetime.now(timezone.utc)
        out[F_POTIONS] = [[p.kind, p.tier] for p in await potion_repo.list_for_user(session, target_id) if p.tier and p.expires_at > now]
    if F_WALLET in fields:
        from bot.services.business import get_wallet

        wallet = await get_wallet(session, target_id)
        out[F_WALLET] = [wallet.nh_coins, round(wallet.per_minute)] if wallet else [0, 0]
    if F_BUSINESS in fields:
        out[F_BUSINESS] = sorted((await business_repo.count_by_type(session, target_id)).items(), key=lambda kv: -kv[1])
    if F_BATTLES in fields:
        out[F_BATTLES] = [[t.isoformat(), x] for t, x in await activity_repo.recent(session, target_id, (ACT_BATTLE,), 5)]
    if F_COOLDOWNS in fields:
        out[F_COOLDOWNS] = max(0, int(await redis.ttl(battle_cooldown(target_id))))
    if F_CLAN in fields:
        member = await clan_repo.get_member(session, target_id)
        clan = await clan_repo.get(session, member.clan_id) if member else None
        out[F_CLAN] = [clan.name, member.rank] if clan else None
    if F_CHALLENGES in fields:
        from bot.db.repositories.district import challenge as challenge_repo

        pending = await challenge_repo.get_pending_for_attacker(session, target_id)
        out[F_CHALLENGES] = 1 if pending else 0
    return out


def _blur(field: str, value):
    """Вилка (уровни равны): числа — диапазон ±15%, списки — только количество, коды — без уровня."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return [int(value * (1 - _RANGE_SPREAD)), int(value * (1 + _RANGE_SPREAD))]
    if field in (F_BLOODLINE, F_PATH, F_TECHNIQUE, F_GENIUS) and isinstance(value, list):
        return [value[0], None]
    if field == F_WALLET and isinstance(value, list):
        return [[int(v * (1 - _RANGE_SPREAD)), int(v * (1 + _RANGE_SPREAD))] for v in value]
    if isinstance(value, list):
        return len(value)
    return value


async def scout(session: AsyncSession, redis: Redis, viewer_id: int, *, target_id: int | None = None,
                username: str | None = None) -> ScoutResult:
    """Разведать игрока. Коммитит (снимок + «Ответный удар»)."""
    viewer_build = await get_build(session, viewer_id)
    levels = _levels(viewer_build)
    if not levels:
        raise NoScoutError
    target = await get_by_id(session, target_id) if target_id is not None else await find_by_username(session, (username or "").lstrip("@"))
    if target is None or target.id == viewer_id:
        raise ScoutTargetError
    target_build = await get_build(session, target.id)
    tpos = target_build.positions or NO_EFFECTS
    vpos = viewer_build.positions or NO_EFFECTS
    hide = tpos.hide
    see_fakes = bool(vpos.get("see_through_fakes"))
    exact_ranges = bool(vpos.get("range_as_exact"))
    fake = 0.0 if see_fakes else tpos.get("fake_numbers")

    visible = {f for f, lv in levels.items() if lv >= hide.get(f, 0)}
    values = await _values(session, redis, target.id, visible - {F_FORECAST})
    payload: dict = {}
    for field, lv in levels.items():
        h = hide.get(field, 0)
        seen = SEEN_EXACT if lv > h else SEEN_RANGE if lv == h else SEEN_HIDDEN
        if seen == SEEN_RANGE and exact_ranges:
            seen = SEEN_EXACT
        if seen == SEEN_HIDDEN:
            payload[field] = {"seen": seen}
            continue
        if field == F_FORECAST:
            payload[field] = {"seen": seen, "value": await _forecast(session, viewer_id, target.id, lv)}
            continue
        value = values.get(field)
        if fake and isinstance(value, (int, float)) and not isinstance(value, bool):
            value = int(value * _fake(viewer_id, target.id, field, fake))
        payload[field] = {"seen": seen, "value": _blur(field, value) if seen == SEEN_RANGE else value}
    label = target.display_name or (f"@{target.username}" if target.username else str(target.id))
    payload["_target"] = label

    trap_lost = 0
    if tpos.get("scout_trap"):
        trap_lost = await _trap(session, viewer_id, tpos.get("scout_trap"))
    created = await scout_repo.save(session, viewer_id, target.id, payload)
    await session.commit()
    notify = "double_agent" if tpos.get("reveal_scout") else "alarm" if tpos.get("scout_alert") else None
    return ScoutResult(target.id, label, created, payload, notify_target=notify, trap_lost=trap_lost)


async def _trap(session: AsyncSession, viewer_id: int, share: float) -> int:
    """«Ответный удар»: разведчик теряет долю самой слабой стопки лагеря атаки."""
    from bot.services.district.army import apply_losses

    stacks = await load_camp(session, viewer_id, CAMP_ATTACK, for_update=True)
    if not stacks:
        return 0
    weakest = min(stacks, key=lambda s: s.unit_power)
    lost = int(weakest.quantity * min(0.5, share))
    if lost:
        await apply_losses(session, viewer_id, CAMP_ATTACK, {weakest.key: lost})
    return lost


async def _forecast(session: AsyncSession, viewer_id: int, target_id: int, level: int) -> list[float] | None:
    """Прогноз боя разведчика с целью: [шанс победы, доля потерь]; точность растёт с уровнем."""
    from bot.services.foresight.foresight import _simulate
    from bot.services.characteristic import get_combat_profile

    me = await load_camp(session, viewer_id, CAMP_ATTACK, for_update=False)
    them = await load_camp(session, target_id, CAMP_DEFENSE, for_update=False)
    if not me or not them:
        return None
    a = await get_combat_profile(session, viewer_id)
    d = await get_combat_profile(session, target_id)
    f = _simulate(me, a.chances(role="attack"), them, d.chances(role="defense"), max(1, min(3, (level + 1) // 3)))
    return [round(f.win_rate, 2), round(f.loss_share, 2)]


async def levels_for(session: AsyncSession, user_id: int) -> dict[str, int]:
    """Поля, которые разведка игрока вообще может открыть (поле → уровень)."""
    return _levels(await get_build(session, user_id))


async def get_saved(session: AsyncSession, viewer_id: int, target_id: int):
    return await scout_repo.get(session, viewer_id, target_id)


async def list_saved(session: AsyncSession, viewer_id: int):
    return await scout_repo.recent(session, viewer_id, REPORTS_SHOWN)


async def has_report(session: AsyncSession, viewer_id: int, target_id: int) -> bool:
    return await scout_repo.exists(session, viewer_id, target_id)
