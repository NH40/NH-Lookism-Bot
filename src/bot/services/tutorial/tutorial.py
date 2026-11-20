"""Лига-обучение (сервис, пользователь 2026-11-19). Дизайн — `config/tutorial`.

Новичок проходит обязательно: пока не выпустился, бои за настоящую территорию закрыты (`ensure_not_locked` в
точках атаки), на настоящей карте у него ничего нет — значит, и напасть на него не за что. Старые игроки
(`legacy`) проходят добровольно, оставаясь в своей лиге. Бои на учебной карте — настоящий движок против
ботов, потери настоящие; здания строятся за настоящие NHCoin (первое кафе бесплатно), доход — по настоящей
формуле на настоящий счёт. Вербовка, развитие, родословная, мастерство — настоящие системы, шаг проверяет
их состояние. После выпуска учебная карта стирается, остаётся всё, кроме неё.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from bot.config import tutorial as cfg
from bot.constant.business import BIZ_CAFE
from bot.constant.ledger import REASON_INCOME
from bot.constant.resource import RES_COINS
from bot.db.models.tutorial import TutorialRun as TrainingRun
from bot.db.models.user import User
from bot.services.country import BattlesClosedError
from bot.utils.log_context import coin_reason

STATUS_LEGACY = "legacy"
STATUS_ACTIVE = "active"
STATUS_DONE = "done"


class TrainingError(Exception):
    def __init__(self, code: str, value: int = 0) -> None:
        super().__init__(code)
        self.code, self.value = code, value


class TrainingLockError(BattlesClosedError):
    """Бои за настоящую территорию — после обучения. Ловится общим обработчиком запрета боёв."""

    def __init__(self) -> None:
        from bot.texts.tutorial import LOCKED_ALERT

        super().__init__("")
        self.alert = LOCKED_ALERT


@dataclass(frozen=True, slots=True)
class CityState:
    index: int
    name: str
    owned: list[bool]
    buildings: list[int]
    bot_rank: str
    bots: int
    whole: bool
    open: bool  # можно нападать (предыдущий город взят целиком)


@dataclass(frozen=True, slots=True)
class TrainingView:
    status: str
    voluntary: bool
    step: int  # индекс текущего шага; == len(STEPS) — пройдено
    code: str | None
    cities: list[CityState]
    cooldown: int
    pending_income: int
    capacity: int


@dataclass(frozen=True, slots=True)
class FightReport:
    won: bool
    captured: int  # сколько районов взято
    city: str
    attackers: int
    dead: int
    bots: int


@dataclass(frozen=True, slots=True)
class Advance:
    done: list[str]  # закрытые шаги
    rewards: dict[str, int]
    finished: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cd_key(user_id: int) -> str:
    return f"tutorial:cd:{user_id}"


def _new_map() -> dict:
    return {"c": [{"o": [False] * c.districts, "b": [0] * c.districts} for c in cfg.TRAINING_CITIES], "flags": {}}


async def get_run(session: AsyncSession, user_id: int, *, for_update: bool = False) -> TrainingRun | None:
    stmt = select(TrainingRun).where(TrainingRun.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def is_locked(session: AsyncSession, user_id: int) -> bool:
    """Обязательное обучение не пройдено — настоящие бои за территорию закрыты."""
    return bool(await session.scalar(
        select(func.count()).select_from(TrainingRun).where(
            TrainingRun.user_id == user_id, TrainingRun.status == STATUS_ACTIVE, TrainingRun.voluntary.is_(False)
        )
    ))


async def ensure_not_locked(session: AsyncSession, user_id: int) -> None:
    if await is_locked(session, user_id):
        raise TrainingLockError


async def _baseline(session: AsyncSession, user_id: int) -> dict:
    from bot.db.repositories.extra.extra import total_quantity

    stats = await session.scalar(
        select(User.stat_strength + User.stat_speed + User.stat_endurance + User.stat_agility).where(User.id == user_id)
    )
    return {"statists": int(await total_quantity(session, user_id) or 0), "stats": int(stats or 0)}


async def _begin(session: AsyncSession, run: TrainingRun, user_id: int, *, voluntary: bool) -> None:
    from bot.services.extra.extra import recruit_into_stack

    run.status, run.voluntary, run.step = STATUS_ACTIVE, voluntary, 0
    run.map, run.accrued_at, run.started_at, run.finished_at = _new_map(), None, _now(), None
    if not voluntary:  # новичку — учебный отряд, иначе первый бой не с кем начинать
        rank, qty = cfg.TRAINING_START_SQUAD
        await recruit_into_stack(session, user_id, rank, qty)
    run.base = await _baseline(session, user_id)


async def start_if_new(session: AsyncSession, user_id: int) -> bool:
    """Новый игрок (строки ещё нет) — обязательное обучение. → начато ли. Коммитит."""
    if await get_run(session, user_id) is not None:
        return False
    run = TrainingRun(user_id=user_id, status=STATUS_ACTIVE)
    session.add(run)
    await _begin(session, run, user_id, voluntary=False)
    await session.commit()
    return True


async def start_voluntary(session: AsyncSession, user_id: int) -> None:
    """Старый игрок проходит гайд ради награды, оставаясь в своей лиге (один раз). Коммитит."""
    run = await get_run(session, user_id, for_update=True)
    if run is None:
        run = TrainingRun(user_id=user_id, status=STATUS_LEGACY)
        session.add(run)
    if run.status != STATUS_LEGACY:
        await session.rollback()
        raise TrainingError("already")
    await _begin(session, run, user_id, voluntary=True)
    await session.commit()


def _income_counts(run: TrainingRun) -> dict[str, int]:
    return {BIZ_CAFE: sum(sum(c["b"]) for c in run.map["c"])}


async def _pending_income(session: AsyncSession, run: TrainingRun, user_id: int) -> tuple[int, int]:
    from bot.services.business.business import income_for

    if run.accrued_at is None or not _income_counts(run)[BIZ_CAFE]:
        return 0, 0
    minutes = min(int((_now() - run.accrued_at).total_seconds() // 60), cfg.TRAINING_INCOME_CAP_MINUTES)
    level = int(await session.scalar(select(User.business_level).where(User.id == user_id)) or 0)
    return income_for(_income_counts(run), level, minutes, random.Random(f"{user_id}:{run.accrued_at.isoformat()}")), minutes


async def _capacity(session: AsyncSession, user_id: int) -> int:
    from bot.services.business.business import _capacity_per_district

    return _capacity_per_district(int(await session.scalar(select(User.business_capacity).where(User.id == user_id)) or 0))


def _cities(run: TrainingRun) -> list[CityState]:
    out = []
    for i, c in enumerate(cfg.TRAINING_CITIES):
        state = run.map["c"][i]
        prev_full = i == 0 or all(run.map["c"][i - 1]["o"])
        out.append(CityState(i, c.name, list(state["o"]), list(state["b"]), c.bot_rank, c.bots, c.whole, prev_full))
    return out


async def view(session: AsyncSession, redis: Redis, user_id: int) -> TrainingView:
    run = await get_run(session, user_id)
    if run is None:
        return TrainingView(STATUS_LEGACY, True, 0, None, [], 0, 0, 0)
    if run.status != STATUS_ACTIVE or run.map is None:
        return TrainingView(run.status, run.voluntary, len(cfg.TRAINING_STEPS) if run.status == STATUS_DONE else 0, None, [], 0, 0, 0)
    pending, _ = await _pending_income(session, run, user_id)
    code = cfg.TRAINING_STEPS[run.step] if run.step < len(cfg.TRAINING_STEPS) else None
    return TrainingView(run.status, run.voluntary, run.step, code, _cities(run), max(0, await redis.ttl(_cd_key(user_id))),
                        pending, await _capacity(session, user_id))


async def _active(session: AsyncSession, user_id: int) -> TrainingRun:
    run = await get_run(session, user_id, for_update=True)
    if run is None or run.status != STATUS_ACTIVE or run.map is None:
        raise TrainingError("not_active")
    return run


def _touch(run: TrainingRun) -> None:
    flag_modified(run, "map")  # JSONB правится на месте — без отметки SQLAlchemy изменений не увидит


async def attack(session: AsyncSession, redis: Redis, user_id: int, city: int, district: int | None) -> tuple[FightReport, Advance]:
    """Бой на учебной карте: район посёлка или город целиком. Коммитит."""
    from bot.config.characteristic import extra_power_for_rank
    from bot.constant.extra import CAMP_ATTACK
    from bot.constant.position_skill import VS_DISTRICT
    from bot.services.characteristic import get_combat_profile
    from bot.services.combat import CombatStack, base_chances, simulate_battle
    from bot.services.district.army import apply_losses, load_camp
    from bot.services.position_skill.battle import matchup

    run = await _active(session, user_id)
    if not 0 <= city < len(cfg.TRAINING_CITIES):
        raise TrainingError("bad_target")
    spec, state = cfg.TRAINING_CITIES[city], run.map["c"][city]
    if city > 0 and not all(run.map["c"][city - 1]["o"]):
        raise TrainingError("city_closed")
    if spec.whole:
        targets = [i for i, o in enumerate(state["o"]) if not o]
    else:
        if district is None or not 0 <= district < spec.districts:
            raise TrainingError("bad_target")
        targets = [] if state["o"][district] else [district]
    if not targets:
        raise TrainingError("already_mine")
    stacks = await load_camp(session, user_id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise TrainingError("no_army")
    if not await redis.set(_cd_key(user_id), "1", nx=True, ex=cfg.TRAINING_BATTLE_COOLDOWN_SECONDS):
        raise TrainingError("cooldown", max(1, await redis.ttl(_cd_key(user_id))))
    profile = await get_combat_profile(session, user_id)
    defender = [CombatStack(key="bot", unit_power=extra_power_for_rank(spec.bot_rank), quantity=spec.bots)]
    m = matchup(profile, vs=(VS_DISTRICT,), defender_chances=base_chances(), attacker_stacks=stacks)
    result = simulate_battle(stacks, defender, attacker_chances=m.attacker, defender_chances=m.defender)
    await apply_losses(session, user_id, CAMP_ATTACK, result.attacker.dead)
    if result.attacker_won:
        for i in targets:
            state["o"][i] = True
        _touch(run)
    report = FightReport(result.attacker_won, len(targets) if result.attacker_won else 0, spec.name,
                         result.attacker.initial_quantity, result.attacker.total_dead, spec.bots)
    adv = await _advance(session, run, user_id)
    await session.commit()
    return report, adv


async def build(session: AsyncSession, user_id: int, city: int, district: int) -> tuple[int, Advance]:
    """Кафе на своём учебном районе за настоящие NHCoin (первое — бесплатно, как в игре). → цена. Коммитит."""
    from bot.db.repositories import business as business_repo
    from bot.services.business.business import build_cost

    run = await _active(session, user_id)
    if not (0 <= city < len(cfg.TRAINING_CITIES) and 0 <= district < cfg.TRAINING_CITIES[city].districts):
        raise TrainingError("bad_target")
    state = run.map["c"][city]
    if not state["o"][district]:
        raise TrainingError("not_mine")
    if state["b"][district] >= await _capacity(session, user_id):
        raise TrainingError("full")
    await collect(session, user_id, commit=False, run=run)  # доход по старому числу зданий — до стройки
    owned = sum((await business_repo.count_by_type(session, user_id)).values()) + _income_counts(run)[BIZ_CAFE]
    cost = build_cost(BIZ_CAFE, owned_total=owned)
    if cost and not await business_repo.spend_coins(session, user_id, cost):
        await session.rollback()
        raise TrainingError("no_coins", cost)
    state["b"][district] += 1
    if run.accrued_at is None:
        run.accrued_at = _now()
    _touch(run)
    adv = await _advance(session, run, user_id)
    await session.commit()
    return cost, adv


async def collect(session: AsyncSession, user_id: int, *, commit: bool = True, run: TrainingRun | None = None) -> tuple[int, Advance | None]:
    """Забрать доход учебных зданий на настоящий счёт. → (NHCoin, шаги)."""
    from bot.services.resource import grant

    run = run or await _active(session, user_id)
    amount, minutes = await _pending_income(session, run, user_id)
    if minutes > 0:
        run.accrued_at = _now()
    if amount > 0:
        with coin_reason(REASON_INCOME):
            await grant(session, user_id, RES_COINS, amount)
        run.map["flags"]["collected"] = True
        _touch(run)
    if not commit:
        return amount, None
    adv = await _advance(session, run, user_id)
    await session.commit()
    return amount, adv


async def acknowledge(session: AsyncSession, user_id: int) -> Advance:
    """«Понятно» на уроке (гениальность, техники) или «Проверить» на шагах с настоящими системами. Коммитит."""
    run = await _active(session, user_id)
    code = cfg.TRAINING_STEPS[run.step] if run.step < len(cfg.TRAINING_STEPS) else None
    if code in cfg.TRAINING_LESSONS:
        run.map["flags"][code] = True
        _touch(run)
    adv = await _advance(session, run, user_id)
    await session.commit()
    return adv


async def _step_done(session: AsyncSession, run: TrainingRun, user_id: int, code: str) -> bool:
    c = run.map["c"]
    flags = run.map.get("flags", {})
    base = run.base or {}
    if code == cfg.STEP_FIGHT:
        return any(c[0]["o"])
    if code == cfg.STEP_BUILD:
        return _income_counts(run)[BIZ_CAFE] > 0
    if code == cfg.STEP_INCOME:
        return bool(flags.get("collected"))
    if code == cfg.STEP_RECRUIT:
        return (await _baseline(session, user_id))["statists"] > base.get("statists", 0)
    if code == cfg.STEP_POWER:
        return sum(c[0]["o"]) >= cfg.TRAINING_POWER_DISTRICTS
    if code == cfg.STEP_DEVELOP:
        if (await _baseline(session, user_id))["stats"] > base.get("stats", 0):
            return True
        # Все характеристики уже на потолке (Infinity) — вкладывать некуда, шаг засчитан (жалоба игрока 2026-11-20).
        from bot.constant.characteristic import RANK_LADDER

        top = len(RANK_LADDER) - 1
        row = (await session.execute(select(User.stat_strength, User.stat_speed, User.stat_endurance, User.stat_agility)
                                     .where(User.id == user_id))).one_or_none()
        return bool(row) and all(v >= top for v in row)
    if code == cfg.STEP_BLOODLINE:
        return await session.scalar(select(User.bloodline).where(User.id == user_id)) is not None
    if code in cfg.TRAINING_LESSONS:
        return bool(flags.get(code))
    if code == cfg.STEP_CITY:
        return all(c[0]["o"]) and all(c[1]["o"])
    if code == cfg.STEP_COUNTRY:
        return all(c[2]["o"])
    return False


async def _advance(session: AsyncSession, run: TrainingRun, user_id: int) -> Advance:
    """Закрыть все выполненные подряд шаги: награда за каждый, на последнем — выпуск. НЕ коммитит."""
    from bot.services.resource import grant

    done: list[str] = []
    rewards: dict[str, int] = {}
    while run.step < len(cfg.TRAINING_STEPS):
        code = cfg.TRAINING_STEPS[run.step]
        if not await _step_done(session, run, user_id, code):
            break
        for res, n in cfg.TRAINING_REWARDS.get(code, {}).items():
            await grant(session, user_id, res, n)
            rewards[res] = rewards.get(res, 0) + n
        done.append(code)
        run.step += 1
        run.base = await _baseline(session, user_id)
    finished = run.step >= len(cfg.TRAINING_STEPS)
    if finished and run.status == STATUS_ACTIVE:
        if run.map is not None:
            await collect(session, user_id, commit=False, run=run)  # доход учебных зданий — напоследок
        run.status, run.finished_at, run.map = STATUS_DONE, _now(), None
    return Advance(done, rewards, finished)
