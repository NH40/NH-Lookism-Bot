"""Родословная Пеньгуана (сервис): игра через доход (пользователь 2026-11-13).

- Богатство (`wealth`) — очки из дохода в час (логарифм), районов и городов империи. От него — атака,
  бонус к влиянию и (от земель) доход: `build_mods`, его вызывает `services/build` для Пеньгуана.
- Временные бафы на час: Подкуп (реакции врага слабее), Военная казна (+атака), Золотая вербовка
  (+бойцы за вербовку). Цена — часы своего дохода, монеты сгорают.
- Конструктор статистов: ранг, уровень, звёзды, школа и её уровень; дорогой и с суточным лимитом мощи.
- Выкуп павших последнего боя, выкуп района бота без боя, монополия на бирже.
Цены — максимум из «по мощи» и «в часах дохода» (`config/penguan`).
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.characteristic import extra_power_for_rank, statist_unit_power, training_level_cap
from bot.config.contract import CONTRACT_COINS_PER_POWER
from bot.config.game import EXTRA_TRAINING_MAX_STARS
from bot.config.penguan import (
    PG_ATTACK_CAP,
    PG_BUFF_COST_HOURS,
    PG_BUFF_MIN_COST,
    PG_BUFF_SECONDS,
    PG_BUYBACK_MARKUP,
    PG_BUYOUT_COOLDOWN_SECONDS,
    PG_BUYOUT_MARKUP,
    PG_BUYOUT_MIN_HOURS,
    PG_BUYOUT_STEP_DISTRICTS,
    PG_CITY_POINT,
    PG_CITY_POINTS_CAP,
    PG_DAILY_POWER_FLOOR,
    PG_DISTRICTS_PER_POINT,
    PG_FALLEN_SECONDS,
    PG_INCOME_BASE,
    PG_INFLUENCE_CAP,
    PG_LAND_INCOME_CAP,
    PG_MONOPOLY_CUT_CAP,
    PG_RECRUIT_MARKUP,
    PG_REPEAT_STEP,
    PG_SCHOOL_LEVEL_MULT,
    PG_SCHOOL_MULT,
    PG_STAR_MULT,
    PG_STATIST_MARKUP,
    PG_WEALTH_CAP,
)
from bot.config.school import SCHOOL_MAX_LEVEL
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
from bot.constant.penguan import (
    BUFF_BRIBE,
    BUFF_CHEST,
    BUFF_RECRUIT,
    BUFFS,
    key_builder,
    key_buyout_cd,
    key_day,
    key_lock,
)
from bot.constant.school import SCHOOLS
from bot.db.repositories import business as business_repo
from bot.db.repositories import penguan as pg_repo
from bot.db.repositories.extra import add_to_stacks, stack_key
from bot.services.build.mods import NO_ECO, EconomyMods
from bot.services.combat.mods import NO_MODS, CombatMods

_BUFF_SPECIAL = {BUFF_BRIBE: "pg_bribe", BUFF_CHEST: "pg_chest", BUFF_RECRUIT: "pg_recruit"}


class PenguanError(Exception):
    """Ошибка действия Пеньгуана: `code` — ключ текста (`texts/penguan.ERRORS`), `args` — числа."""

    def __init__(self, code: str, *values) -> None:
        super().__init__(code)
        self.code, self.values = code, values


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- богатство и бафы для build ---


@dataclass(frozen=True, slots=True)
class Wealth:
    income: int  # доход зданий в час (без налога и бафов)
    districts: int
    cities: int
    points: float


async def wealth(session: AsyncSession, user_id: int) -> Wealth:
    """Без `get_build` (его вызывает сам build): доход — по зданиям и уровню бизнеса."""
    from bot.db.repositories.district import count_owned
    from bot.db.repositories.empire.war import count_cities
    from bot.services.admin.live_config import get as live_get
    from bot.services.business.business import income_per_minute

    row = await business_repo.get_wallet(session, user_id)
    counts = await business_repo.count_by_type(session, user_id)
    income = int(income_per_minute(counts, row.business_level) * 60 * live_get("income_multiplier")) if row else 0
    districts, cities = await count_owned(session, user_id), await count_cities(session, user_id)
    points = (
        math.log10(max(1.0, income / PG_INCOME_BASE))
        + districts / PG_DISTRICTS_PER_POINT
        + min(PG_CITY_POINTS_CAP, cities * PG_CITY_POINT)
    )
    return Wealth(income, districts, cities, min(PG_WEALTH_CAP, points))


async def build_mods(session: AsyncSession, user_id: int, special: dict) -> tuple[CombatMods, EconomyMods]:
    """Бафы Пеньгуана для билда: от богатства и от купленных временных бафов."""
    combat, eco = NO_MODS, NO_ECO
    if special.get("pg_attack") or special.get("pg_influence") or special.get("pg_land_income"):
        w = await wealth(session, user_id)
        combat = combat + CombatMods(attack=min(PG_ATTACK_CAP, special.get("pg_attack", 0.0) * w.points))
        land = special.get("pg_land_income", 0.0) * w.districts / 10 + special.get("pg_city_income", 0.0) * w.cities
        eco = eco + EconomyMods(
            influence_bonus=min(PG_INFLUENCE_CAP, special.get("pg_influence", 0.0) * w.points),
            income=min(PG_LAND_INCOME_CAP, land),
        )
    buffs = await pg_repo.active_buffs(session, user_id, _now())
    if BUFF_BRIBE in buffs:
        combat = combat + CombatMods(suppress=buffs[BUFF_BRIBE][0])
    if BUFF_CHEST in buffs:
        combat = combat + CombatMods(attack=buffs[BUFF_CHEST][0])
    if BUFF_RECRUIT in buffs:
        eco = eco + EconomyMods(recruit_quantity=buffs[BUFF_RECRUIT][0])
    return combat, eco


# --- общее ---


async def _pg(session: AsyncSession, user_id: int) -> dict:
    from bot.services.build import get_build

    return (await get_build(session, user_id)).pg


async def hourly_income(session: AsyncSession, user_id: int) -> int:
    """Доход в час «как на экране кошелька» (после налога и бафов) — для цен в часах дохода."""
    from bot.services.business import get_wallet

    w = await get_wallet(session, user_id)
    return int(w.per_minute * 60) if w else 0


async def _lock(redis: Redis, user_id: int) -> str:
    key = key_lock(user_id)
    if not await redis.set(key, "1", nx=True, ex=15):
        raise PenguanError("busy")
    return key


async def _pay(session: AsyncSession, user_id: int, price: int) -> None:
    if not await business_repo.spend_coins(session, user_id, price):
        raise PenguanError("no_coins", price)


# --- временные бафы ---


@dataclass(frozen=True, slots=True)
class BuffOffer:
    kind: str
    power: float  # сила при покупке
    price: int
    active_until: datetime | None


async def buff_offers(session: AsyncSession, user_id: int) -> list[BuffOffer]:
    special = await _pg(session, user_id)
    income = await hourly_income(session, user_id)
    active = await pg_repo.active_buffs(session, user_id, _now())
    offers = []
    for kind in BUFFS:
        power = special.get(_BUFF_SPECIAL[kind], 0.0)
        if not power:
            continue
        price = max(PG_BUFF_MIN_COST, PG_BUFF_COST_HOURS[kind] * income)
        if kind == BUFF_RECRUIT:
            price = max(price, await _recruit_floor(session, user_id, power))
        offers.append(BuffOffer(kind, power, price, active[kind][1] if kind in active else None))
    return offers


async def _recruit_floor(session: AsyncSession, user_id: int, power: float) -> int:
    """Цена Золотой вербовки по мощи: лишние бойцы за час вербовок × цена контракта × наценка."""
    from bot.constant.admin.live_config import KEY_CD_RECRUIT  # тот же КД, что у вербовки
    from bot.db.repositories.phase import get_phase
    from bot.services.admin.live_config import cooldown_seconds
    from bot.services.characteristic import get_combat_profile
    from bot.services.recruit import get_offer

    phase = (await get_phase(session, user_id))[0]
    offer = await get_offer(session, user_id, phase)
    profile = await get_combat_profile(session, user_id)
    per_hour = 3600 / max(1, profile.cooldown(cooldown_seconds(KEY_CD_RECRUIT), profile.eco.recruit_cooldown))
    extra_units = offer.crowd * power * per_hour
    return int(extra_units * extra_power_for_rank(offer.ceiling) / 2 * CONTRACT_COINS_PER_POWER * PG_RECRUIT_MARKUP)


async def buy_buff(session: AsyncSession, redis: Redis, user_id: int, kind: str) -> BuffOffer:
    """Купить баф на час (повторная покупка — продлевает от текущего конца). Коммитит."""
    key = await _lock(redis, user_id)
    try:
        offer = next((o for o in await buff_offers(session, user_id) if o.kind == kind), None)
        if offer is None:
            raise PenguanError("locked")
        await _pay(session, user_id, offer.price)
        start = max(_now(), offer.active_until or _now())
        await pg_repo.set_buff(session, user_id, kind, offer.power, start + timedelta(seconds=PG_BUFF_SECONDS))
        await session.commit()
        return offer
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- конструктор статистов ---


@dataclass(frozen=True, slots=True)
class Design:
    rank: str
    level: int = 0
    stars: int = 0
    school: str = ""
    school_level: int = 0


@dataclass(frozen=True, slots=True)
class BuilderView:
    design: Design
    ceiling: str
    level_cap: int
    unit_power: float
    unit_price: int
    bought_today: int  # мощи
    daily_cap: int  # мощи
    max_units: int  # сколько ещё можно сегодня


def _day() -> str:
    return _now().strftime("%Y-%m-%d")


async def _design(redis: Redis, user_id: int, ceiling: str) -> Design:
    raw = await redis.get(key_builder(user_id))
    try:
        d = Design(**json.loads(raw)) if raw else Design(rank=ceiling)
    except (TypeError, ValueError):
        d = Design(rank=ceiling)
    return d


def _clamp(d: Design, ceiling: str) -> Design:
    rank = d.rank if d.rank in RANK_INDEX and RANK_INDEX[d.rank] <= RANK_INDEX[ceiling] else ceiling
    school = d.school if d.school in SCHOOLS else ""
    return Design(
        rank=rank,
        level=max(0, min(d.level, training_level_cap(rank))),
        stars=max(0, min(d.stars, EXTRA_TRAINING_MAX_STARS)),
        school=school,
        school_level=max(0, min(d.school_level, SCHOOL_MAX_LEVEL)) if school else 0,
    )


def unit_price(d: Design, purchases_today: int) -> tuple[float, int]:
    power = statist_unit_power(d.rank, d.stars, d.level, d.school, d.school_level)
    mult = PG_STATIST_MARKUP * PG_STAR_MULT ** d.stars * (1 + PG_REPEAT_STEP * purchases_today)
    if d.school:
        mult *= PG_SCHOOL_MULT * PG_SCHOOL_LEVEL_MULT ** d.school_level
    return power, max(1, int(power * CONTRACT_COINS_PER_POWER * mult))


async def builder_view(session: AsyncSession, redis: Redis, user_id: int) -> BuilderView:
    from bot.services.contract import terms
    from bot.services.extra import get_army_stats

    share = (await _pg(session, user_id)).get("pg_constructor", 0.0)
    if not share:
        raise PenguanError("locked")
    ceiling = (await terms(session, user_id)).ceiling
    d = _clamp(await _design(redis, user_id, ceiling), ceiling)
    day = await redis.hgetall(key_day(user_id, _day()))
    bought = int(day.get(b"power", day.get("power", 0)) or 0)
    count = int(day.get(b"count", day.get("count", 0)) or 0)
    cap = max(PG_DAILY_POWER_FLOOR, int((await get_army_stats(session, user_id)).total_power * share))
    power, price = unit_price(d, count)
    left = max(0, cap - bought)
    return BuilderView(d, ceiling, training_level_cap(d.rank), power, price, bought, cap, int(left // power) if power else 0)


async def change_design(redis: Redis, session: AsyncSession, user_id: int, param: str, delta: int) -> None:
    from bot.constant.penguan import P_LEVEL, P_RANK, P_SCHOOL, P_SCHOOL_LEVEL, P_STARS
    from bot.services.contract import terms

    ceiling = (await terms(session, user_id)).ceiling
    d = _clamp(await _design(redis, user_id, ceiling), ceiling)
    if param == P_RANK:
        i = max(0, min(RANK_INDEX[ceiling], RANK_INDEX[d.rank] + delta))
        d = Design(RANK_LADDER[i], d.level, d.stars, d.school, d.school_level)
    elif param == P_LEVEL:
        d = Design(d.rank, d.level + delta, d.stars, d.school, d.school_level)
    elif param == P_STARS:
        d = Design(d.rank, d.level, d.stars + delta, d.school, d.school_level)
    elif param == P_SCHOOL:
        order = ("", *SCHOOLS)
        d = Design(d.rank, d.level, d.stars, order[(order.index(d.school) + delta) % len(order)], d.school_level or 1)
    elif param == P_SCHOOL_LEVEL:
        d = Design(d.rank, d.level, d.stars, d.school, d.school_level + delta)
    d = _clamp(d, ceiling)
    await redis.set(key_builder(user_id), json.dumps(asdict(d)), ex=7 * 86400)


async def buy_statists(session: AsyncSession, redis: Redis, user_id: int, quantity: int) -> tuple[int, int]:
    """Купить `quantity` статистов по текущему чертежу (лагерь атаки). → (сколько, цена). Коммитит."""
    key = await _lock(redis, user_id)
    try:
        view = await builder_view(session, redis, user_id)
        quantity = min(quantity, view.max_units)
        if quantity <= 0:
            raise PenguanError("daily_cap", view.daily_cap)
        price = view.unit_price * quantity
        await _pay(session, user_id, price)
        d = view.design
        await add_to_stacks(session, {stack_key(user_id, CAMP_ATTACK, d.rank, d.stars, d.level, d.school, d.school_level): quantity})
        await session.commit()
        day = key_day(user_id, _day())
        await redis.hincrby(day, "power", int(view.unit_power * quantity))
        await redis.hincrby(day, "count", 1)
        await redis.expire(day, 2 * 86400)
        return quantity, price
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- выкуп павших ---


async def remember_fallen(session: AsyncSession, user_id: int, camp: str, dead: dict) -> None:
    """После боя: павшие статисты Пеньгуана с выкупом (`services/absolute.after_battle`). НЕ коммитит."""
    if not (await _pg(session, user_id)).get("pg_buyback"):
        return
    rows = [[*key[1:], n] for key, n in dead.items() if isinstance(key, tuple) and len(key) == 6 and n > 0]
    if rows:
        await pg_repo.set_fallen(session, user_id, camp, rows, _now() + timedelta(seconds=PG_FALLEN_SECONDS))


@dataclass(frozen=True, slots=True)
class BuybackOffer:
    units: int
    power: int
    price: int
    camp: str
    rows: tuple  # (rank, stars, level, school, school_level, n)


async def buyback_offer(session: AsyncSession, user_id: int, *, take: bool = False) -> BuybackOffer | None:
    """Что можно выкупить из последнего боя. `take` — забрать запись (покупка)."""
    share = (await _pg(session, user_id)).get("pg_buyback", 0.0)
    fallen = await pg_repo.take_fallen(session, user_id, _now(), delete_row=take) if share else None
    if fallen is None:
        return None
    camp, raw_rows = fallen
    rows, units, power = [], 0, 0.0
    for rank, stars, level, school, school_level, n in raw_rows:
        take = int(n * min(1.0, share))
        if take:
            rows.append((rank, stars, level, school, school_level, take))
            units += take
            power += statist_unit_power(rank, stars, level, school, school_level) * take
    if not units:
        return None
    price = int(power * CONTRACT_COINS_PER_POWER * PG_BUYBACK_MARKUP)
    return BuybackOffer(units, int(power), price, camp, tuple(rows))


async def buyback(session: AsyncSession, redis: Redis, user_id: int) -> BuybackOffer:
    key = await _lock(redis, user_id)
    try:
        offer = await buyback_offer(session, user_id, take=True)
        if offer is None:
            raise PenguanError("no_fallen")
        await _pay(session, user_id, offer.price)
        camp = offer.camp if offer.camp in (CAMP_ATTACK, CAMP_DEFENSE) else CAMP_ATTACK
        deltas: dict = {}
        for rank, stars, level, school, school_level, n in offer.rows:
            k = stack_key(user_id, camp, rank, stars, level, school, school_level)
            deltas[k] = deltas.get(k, 0) + n
        await add_to_stacks(session, deltas)
        await session.commit()
        return offer
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- выкуп района бота ---


@dataclass(frozen=True, slots=True)
class BuyoutOffer:
    price: int
    cooldown: int  # секунд до следующего выкупа


async def buyout_offer(session: AsyncSession, redis: Redis, user) -> BuyoutOffer | None:
    if not (await _pg(session, user.id)).get("pg_buyout"):
        return None
    from bot.db.repositories.district import count_owned
    from bot.services.city import get_city
    from bot.services.district.district import _bot_army

    city = await get_city(session, user.city_id)
    rank, quantity = _bot_army(city.district_count)
    by_power = extra_power_for_rank(rank) * quantity * CONTRACT_COINS_PER_POWER * PG_BUYOUT_MARKUP
    by_income = PG_BUYOUT_MIN_HOURS * await hourly_income(session, user.id)
    owned = await count_owned(session, user.id)
    price = int(max(by_power, by_income) * (1 + owned / PG_BUYOUT_STEP_DISTRICTS))
    return BuyoutOffer(price, max(0, await redis.ttl(key_buyout_cd(user.id))))


async def buyout(session: AsyncSession, redis: Redis, user) -> tuple[int, int, str | None]:
    """Купить район бота в своём городе без боя. → (номер района, цена, новая фаза или None). Коммитит."""
    from bot.services.business import accrue
    from bot.services.country import ensure_battles_open
    from bot.services.district.throne import promote_or_throne
    from bot.services.phase import is_city_conqueror, is_emperor
    from bot.db.repositories.district import capture_from_bots

    if is_emperor(user.phase) or is_city_conqueror(user.phase):
        raise PenguanError("phase")
    await ensure_battles_open(session, user.country_code)
    key = await _lock(redis, user.id)
    try:
        offer = await buyout_offer(session, redis, user)
        if offer is None:
            raise PenguanError("locked")
        if offer.cooldown:
            raise PenguanError("cooldown", offer.cooldown)
        target = await pg_repo.lock_bot_district(session, user.city_id)
        if target is None:
            raise PenguanError("no_district")
        await _pay(session, user.id, offer.price)
        await accrue(session, user.id)
        if not await capture_from_bots(session, target[0], user.id):
            raise PenguanError("no_district")
        promoted, _, _ = await promote_or_throne(session, user.id, user.city_id)
        await session.commit()
        await redis.set(key_buyout_cd(user.id), "1", ex=PG_BUYOUT_COOLDOWN_SECONDS)
        return target[1], offer.price, promoted
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- монополия (биржа) ---


async def exchange_fee(session: AsyncSession, seller_id: int, fee: float) -> tuple[float, int | None, float]:
    """Комиссия продавца с учётом Пеньгуана → (доля комиссии продавца, император-Пеньгуан или None,
    доля комиссии, уходящая этому императору). Комиссия не создаёт денег: доля императора — из неё."""
    from bot.db.repositories.empire import get_tax_context

    own = (await _pg(session, seller_id)).get("pg_monopoly", 0.0)
    fee *= 1 - min(PG_MONOPOLY_CUT_CAP, own)
    tax = await get_tax_context(session, seller_id)
    if tax is None:
        return fee, None, 0.0
    share = (await _pg(session, tax.emperor_id)).get("pg_monopoly_share", 0.0)
    return fee, (tax.emperor_id if share else None), min(1.0, share)
