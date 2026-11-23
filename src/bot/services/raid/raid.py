"""Рейды на игроков (сервис, пользователь 2026-11-19). Баланс — `config/raid`.

Фоновый проход (`sweep`): назначает рейды подходящим игрокам (есть районы, заходил за 3 дня, не в обязательном
обучении, лимит в сутки и интервал) и разыгрывает просроченные. Игрок, получив пуш, может встретить рейд раньше
(`fight`, онлайн — `services/arena.start_raid`). Каждый бой — своя транзакция.

2026-11-24 (пользователь): рейд всегда бьёт по БОЛЕЕ СИЛЬНОМУ лагерю (`target_camp`: больше мощи, при равенстве —
больше статистов) — и заранее, и по сроку. Раньше по сроку бился лагерь защиты: держали его пустым и отдавали
район, сильный лагерь атаки рейд не трогал.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import raid as cfg
from bot.db.models.raid import Raid

STATUS_PENDING, STATUS_WON, STATUS_LOST = "pending", "won", "lost"


class RaidError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RaidOutcome:
    raid_id: int
    user_id: int
    difficulty: str
    won: bool
    camp: str
    dead: int
    rewards: dict[str, int]
    districts_lost: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def pending_of(session: AsyncSession, user_id: int) -> Raid | None:
    return await session.scalar(select(Raid).where(Raid.user_id == user_id, Raid.status == STATUS_PENDING))


async def _eligible(session: AsyncSession) -> list[int]:
    rows = await session.execute(text("""
        SELECT u.id FROM users u
        WHERE u.last_active_at > now() - make_interval(days => :days)
          AND EXISTS (SELECT 1 FROM districts d WHERE d.owner_id = u.id)
          AND NOT EXISTS (SELECT 1 FROM tutorial_runs t WHERE t.user_id = u.id AND t.status = 'active' AND NOT t.voluntary)
          AND NOT EXISTS (SELECT 1 FROM raids r WHERE r.user_id = u.id AND r.status = 'pending')
          AND NOT EXISTS (SELECT 1 FROM raids r WHERE r.user_id = u.id AND r.created_at > now() - make_interval(hours => :gap))
          AND (SELECT count(*) FROM raids r WHERE r.user_id = u.id AND r.created_at > now() - interval '1 day') < :per_day
    """), {"days": cfg.RAID_ACTIVE_DAYS, "gap": cfg.RAID_MIN_GAP_HOURS, "per_day": cfg.RAID_PER_DAY})
    return [int(u) for (u,) in rows.all()]


def _pick_difficulty(rng: random.Random) -> str:
    codes = list(cfg.RAID_DIFFICULTIES)
    return rng.choices(codes, weights=[cfg.RAID_DIFFICULTIES[c][0] for c in codes])[0]


async def spawn(session_factory: async_sessionmaker[AsyncSession], rng: random.Random | None = None) -> list[Raid]:
    """Назначить рейды (с шансом) подходящим игрокам. → новые рейды (для пушей)."""
    from bot.services.extra import get_army_stats

    rng = rng or random.Random()
    async with session_factory() as session:
        ids = [u for u in await _eligible(session) if rng.random() < cfg.RAID_CHANCE_PER_SWEEP]
    created = []
    for uid in ids:
        async with session_factory() as session:
            difficulty = _pick_difficulty(rng)
            power = int((await get_army_stats(session, uid)).total_power * cfg.RAID_DIFFICULTIES[difficulty][1])
            raid = Raid(user_id=uid, difficulty=difficulty, power=max(power, 100), status=STATUS_PENDING,
                        starts_at=_now() + timedelta(seconds=cfg.RAID_WARNING_SECONDS))
            session.add(raid)
            await session.commit()
            created.append(raid)
    return created


async def target_camp(session: AsyncSession, user_id: int) -> str:
    """Лагерь, по которому бьёт рейд: больше мощи, при равенстве — больше статистов; оба пусты — защиты."""
    from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
    from bot.services.district.army import load_camp

    def score(stacks) -> tuple[float, int]:
        return sum(s.unit_power * s.quantity for s in stacks), sum(s.quantity for s in stacks)

    attack = score(await load_camp(session, user_id, CAMP_ATTACK, for_update=False))
    defense = score(await load_camp(session, user_id, CAMP_DEFENSE, for_update=False))
    return CAMP_ATTACK if attack > defense else CAMP_DEFENSE


async def _resolve(session: AsyncSession, raid: Raid, camp: str, result_override=None) -> RaidOutcome:
    """Бой рейда против лагеря игрока. НЕ проверяет статус — вызывающий держит строку под блокировкой. Коммитит."""
    from bot.constant.position_skill import VS_DISTRICT
    from bot.services.business import accrue
    from bot.services.characteristic import get_combat_profile
    from bot.services.combat import CombatStack, base_chances, simulate_battle
    from bot.services.district.army import apply_losses, load_camp
    from bot.services.position_skill.battle import matchup
    from bot.services.resource import grant

    uid = raid.user_id
    stacks = await load_camp(session, uid, camp, for_update=True)
    enemy = [CombatStack(key="raid", unit_power=max(1.0, raid.power / cfg.RAID_STACK_SIZE), quantity=cfg.RAID_STACK_SIZE)]
    won, dead = False, 0
    if stacks:
        profile = await get_combat_profile(session, uid)
        m = matchup(profile, vs=(VS_DISTRICT,), defender_chances=base_chances(), attacker_stacks=stacks)
        result = result_override or simulate_battle(stacks, enemy, attacker_chances=m.attacker, defender_chances=m.defender)
        await apply_losses(session, uid, camp, result.attacker.dead)
        won, dead = result.attacker_won, result.attacker.total_dead
    rewards: dict[str, int] = {}
    lost = 0
    if won:
        rewards = dict(cfg.RAID_REWARDS[raid.difficulty])
        from bot.constant.resource import RES_COINS
        from bot.services.business import get_wallet

        wallet = await get_wallet(session, uid)
        hourly = float(wallet.per_minute) * 60 if wallet else 0.0
        rewards[RES_COINS] = max(rewards.get(RES_COINS, 0), int(hourly * cfg.RAID_COIN_HOURS[raid.difficulty]))
        for res, n in rewards.items():
            await grant(session, uid, res, n)
    else:
        await accrue(session, uid)  # доход по старым районам — до потери
        n = cfg.RAID_DIFFICULTIES[raid.difficulty][2]
        ids = [int(d) for (d,) in (await session.execute(
            text("SELECT id FROM districts WHERE owner_id = :u ORDER BY random() LIMIT :n"), {"u": uid, "n": n}
        )).all()]
        if ids:
            await session.execute(text("DELETE FROM businesses WHERE district_id = ANY(:d)"), {"d": ids})
            await session.execute(text("UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE id = ANY(:d)"), {"d": ids})
        lost = len(ids)
    raid.status = STATUS_WON if won else STATUS_LOST
    raid.resolved_at = _now()
    raid.result = {"camp": camp, "dead": dead, "rewards": rewards, "lost": lost}
    out = RaidOutcome(raid.id, uid, raid.difficulty, won, camp, dead, rewards, lost)
    await session.commit()
    return out


async def fight(session: AsyncSession, user_id: int) -> RaidOutcome:
    """Игрок встречает свой рейд, не дожидаясь срока, — бьётся более сильный лагерь. Коммитит."""
    raid = await session.scalar(select(Raid).where(Raid.user_id == user_id, Raid.status == STATUS_PENDING).with_for_update())
    if raid is None:
        raise RaidError("no_raid")
    return await _resolve(session, raid, await target_camp(session, user_id))


async def resolve_due(session_factory: async_sessionmaker[AsyncSession]) -> list[RaidOutcome]:
    """Просроченные рейды — бьётся более сильный лагерь игрока."""
    async with session_factory() as session:
        ids = [int(i) for (i,) in (await session.execute(
            select(Raid.id).where(Raid.status == STATUS_PENDING, Raid.starts_at <= _now())
        )).all()]
    out = []
    for rid in ids:
        async with session_factory() as session:
            raid = await session.scalar(select(Raid).where(Raid.id == rid, Raid.status == STATUS_PENDING).with_for_update(skip_locked=True))
            if raid is not None:
                out.append(await _resolve(session, raid, await target_camp(session, raid.user_id)))
    return out


def raid_enemy(raid: Raid) -> list:
    from bot.services.combat import CombatStack

    return [CombatStack(key="raid", unit_power=max(1.0, raid.power / cfg.RAID_STACK_SIZE), quantity=cfg.RAID_STACK_SIZE)]


async def settle_online(session: AsyncSession, raid_id: int, result, camp: str | None = None) -> RaidOutcome | None:
    """Итог онлайн-боя с рейдом: рейд ещё pending, срок сдвинут на время боя. `camp` — лагерь, что вышел в бой."""
    from bot.constant.extra import CAMP_ATTACK

    raid = await session.scalar(select(Raid).where(Raid.id == raid_id, Raid.status == STATUS_PENDING).with_for_update())
    if raid is None:
        return None
    return await _resolve(session, raid, camp or CAMP_ATTACK, result_override=result)
