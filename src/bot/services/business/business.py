"""Бизнесы на районе — кофе/зал/магазин/нелегальный рынок/парламент, прокачка уровень/вместимость (сервис).

raw-notes «Карта» → «Бизнес». Подтверждено пользователем 2026-09-29 (AskUserQuestion):
бизнесы захваченного района уходят победителю; доход копится до 24 часов; NHCoin —
отдельная мягкая валюта; тренажёрный зал +1 п.п. к шансам тренировки статистов,
парламент +1 влияние.

**Доход — ленивый, без фонового таска.** `users.coins_accrued_at` — до какого момента
доход уже зачислен. Всё, что меняет доходность (стройка, прокачка уровня, смена владельца
района), сначала вызывает `accrue()` под `FOR UPDATE` строки игрока — иначе новое здание
или захваченный район "заработали" бы задним числом за время до их появления. Экран и
профиль показывают НЕзачисленное (`get_wallet` — чистое чтение, без записи: Mini App
read-only) — игрок забирает его кнопкой «💰 Забрать» (`collect`).

**Хранилище — 24 часа** (`BUSINESS_ACCRUAL_CAP_MINUTES`): если не забирать дольше, доход
за сверх-сутки сгорает и таймер встаёт на "сейчас" (idle-механика: повод заходить раз в
день). Внутри окна отметка сдвигается ровно на целые минуты — неполная минута не теряется.

**Нелегальный рынок — детерминированный по seed** (`user_id` + отметка начисления + число
минут): каждую минуту каждое здание даёт случайное целое `MIN..MAX`. Seed делает прогноз
"накоплено" на экране и фактическое зачисление одним и тем же числом (иначе цифра прыгала
бы при каждом открытии экрана и не совпадала бы с тем, что пришло по кнопке). Большие
объёмы бросков (N > `_EXACT_DRAWS_LIMIT`) — нормальное приближение суммы (ЦПТ), тот же
приём "одна операция вместо цикла по N", что биномиальные броски у тренировки/боя.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.potion import POTION_EFFECTS, POTION_TIERS
from bot.constant.potion import POTION_WEALTH
from bot.db.repositories import potion as potion_repo
from bot.db.repositories import clan as clan_repo
from bot.config.clan import CLAN_DEPUTY_SHARE, CLAN_OWNER_SHARE

from bot.config.game import (
    BUSINESS_ACCRUAL_CAP_MINUTES,
    BUSINESS_BASE_CAPACITY,
    BUSINESS_BLACK_MARKET_MAX,
    BUSINESS_BLACK_MARKET_MIN,
    BUSINESS_BUILD_COST,
    BUSINESS_CAFE_INCOME,
    BUSINESS_CAPACITY_UPGRADE_BASE_COST,
    BUSINESS_GYM_INCOME,
    BUSINESS_GYM_TRAINING_BONUS_PERCENT,
    BUSINESS_LEVEL_INCOME_BONUS_PERCENT,
    BUSINESS_LEVEL_UPGRADE_BASE_COST,
    BUSINESS_MAX_UPGRADE,
    BUSINESS_PARLIAMENT_INCOME,
    BUSINESS_PARLIAMENT_INFLUENCE,
    BUSINESS_SHOP_BASE,
    BUSINESS_SHOP_EXPONENT,
    BUSINESS_SHOP_LINEAR_AFTER,
)
from bot.constant.business import (
    BIZ_BLACK_MARKET,
    BIZ_CAFE,
    BIZ_GYM,
    BIZ_PARLIAMENT,
    BIZ_SHOP,
    BUSINESS_TYPES,
    UPGRADE_CAPACITY,
    UPGRADE_LEVEL,
)
from bot.config.empire import EMPEROR_PASSIVE_BONUS_PERCENT
from bot.db.repositories import business as business_repo
from bot.constant.activity import ACT_BUSINESS
from bot.constant.dev_quest import TASK_BUILD, TASK_COLLECT, TASK_INCOME
from bot.services.dev_quest import emit as quest_event
from bot.services.activity import log as log_activity
from bot.texts.activity import LOG_BUILD, LOG_BUILD_ALL, LOG_DEMOLISH
from bot.texts.business import BUSINESS_NAMES
from bot.services.build import NO_ECO, EconomyMods, capped, get_build
from bot.db.repositories import empire as empire_repo
from bot.db.repositories.empire import TaxContext
from bot.db.repositories.district import get_row

_EXACT_DRAWS_LIMIT = 2000


class UnknownBusinessTypeError(Exception):
    pass


class NotDistrictOwnerError(Exception):
    pass


class NoFreeSlotError(Exception):
    pass


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int, balance: int) -> None:
        self.cost = cost
        self.balance = balance


class MaxUpgradeError(Exception):
    pass


class NothingToDemolishError(Exception):
    pass


# --- чистая математика дохода ---


def _level_multiplier(level: int) -> float:
    return 1 + BUSINESS_LEVEL_INCOME_BONUS_PERCENT * level / 100


def _shop_total_per_minute(shops: float) -> float:
    """Суммарный доход n магазинов = BASE × n^EXPONENT — сверхлинейно до `BUSINESS_SHOP_LINEAR_AFTER`,
    дальше линейно: каждый следующий даёт столько же, сколько последний сверхлинейный."""
    if not shops:
        return 0.0
    cap = BUSINESS_SHOP_LINEAR_AFTER
    if shops <= cap:
        return BUSINESS_SHOP_BASE * shops**BUSINESS_SHOP_EXPONENT
    marginal = BUSINESS_SHOP_BASE * BUSINESS_SHOP_EXPONENT * cap ** (BUSINESS_SHOP_EXPONENT - 1)
    return BUSINESS_SHOP_BASE * cap**BUSINESS_SHOP_EXPONENT + (shops - cap) * marginal


def _fixed_per_minute(counts: dict[str, int]) -> float:
    return (
        counts.get(BIZ_CAFE, 0) * BUSINESS_CAFE_INCOME
        + counts.get(BIZ_GYM, 0) * BUSINESS_GYM_INCOME
        + counts.get(BIZ_PARLIAMENT, 0) * BUSINESS_PARLIAMENT_INCOME
        + _shop_total_per_minute(counts.get(BIZ_SHOP, 0))
    )


def income_per_minute(counts: dict[str, int], level: int) -> float:
    """Ожидаемый доход в минуту — для экрана (рынок — по среднему)."""
    black_market_mean = counts.get(BIZ_BLACK_MARKET, 0) * (BUSINESS_BLACK_MARKET_MIN + BUSINESS_BLACK_MARKET_MAX) / 2
    return (_fixed_per_minute(counts) + black_market_mean) * _level_multiplier(level)


def _black_market_total(draws: int, rng: random.Random) -> int:
    if draws <= 0:
        return 0
    lo, hi = BUSINESS_BLACK_MARKET_MIN, BUSINESS_BLACK_MARKET_MAX
    if draws <= _EXACT_DRAWS_LIMIT:
        return sum(rng.randint(lo, hi) for _ in range(draws))
    # Сумма N независимых равномерных целых lo..hi ≈ N(μ·N, σ²·N), σ² = ((hi-lo+1)²-1)/12.
    mean = draws * (lo + hi) / 2
    sd = math.sqrt(draws * ((hi - lo + 1) ** 2 - 1) / 12)
    return max(draws * lo, min(draws * hi, round(rng.gauss(mean, sd))))


def weighted_counts(counts: dict[str, int], positions) -> dict[str, float]:
    """Навыки Бизнесмена «Своё кафе», «Сеть магазинов»… — доход типа зданий как от большего
    числа зданий (магазины растут по степени — бонус к их числу честнее, чем к сумме)."""
    if positions is None:
        return counts
    return {t: c * (1 + positions.get(f"income_{t}")) for t, c in counts.items()}


def income_for(counts: dict[str, int], level: int, minutes: int, rng: random.Random) -> int:
    if minutes <= 0 or not counts:
        return 0
    black_market = _black_market_total(int(counts.get(BIZ_BLACK_MARKET, 0) * minutes), rng)
    return int((_fixed_per_minute(counts) * minutes + black_market) * _level_multiplier(level))


def _cap_minutes(eco: EconomyMods = NO_ECO) -> int:
    """Хранилище: 24 часа + часы от систем развития (Элита, гений бизнеса)."""
    return BUSINESS_ACCRUAL_CAP_MINUTES + int(eco.storage_hours * 60)


def _accrual_window(accrued_at: datetime, now: datetime, cap_minutes: int = BUSINESS_ACCRUAL_CAP_MINUTES) -> tuple[int, datetime]:
    """(минут к зачислению, новая отметка). Сверх хранилища (24 часа + бафы) — ровно
    хранилище и отметка на "сейчас" (переполнение сгорает); иначе — целые минуты, отметка
    сдвигается на них же."""
    elapsed = (now - accrued_at).total_seconds()
    if elapsed <= 0:
        return 0, accrued_at
    if elapsed >= cap_minutes * 60:
        return cap_minutes, now
    minutes = int(elapsed // 60)
    return minutes, accrued_at + timedelta(minutes=minutes)


def _rng(user_id: int, accrued_at: datetime, minutes: int) -> random.Random:
    return random.Random(f"{user_id}:{accrued_at.isoformat()}:{minutes}")


def _storage_full_in(accrued_at: datetime, now: datetime, cap_minutes: int = BUSINESS_ACCRUAL_CAP_MINUTES) -> int:
    return max(0, int(cap_minutes * 60 - (now - accrued_at).total_seconds()))


def _with_income(gross: int, eco: EconomyMods, potion: float = 0.0) -> int:
    from bot.services.admin.live_config import get as live_get

    gross = int(gross * live_get("income_multiplier"))  # множитель админа «на лету» (превью == начисление)
    bonus = eco.income + potion
    return int(gross * (1 + bonus)) if bonus else gross


async def _wealth_potion_bonus(session: AsyncSession, user_id: int, start: datetime, end: datetime, power: float) -> float:
    """Зелье богатства для ленивого дохода: его прибавка × доля окна начисления, в которую
    зелье действовало (иначе зелье, выпитое перед «Забрать», умножило бы весь суточный
    накоп). Окно последнего выпитого зелья хранится и после окончания действия."""
    window = await potion_repo.get_window(session, user_id, POTION_WEALTH)
    if window is None or end <= start:
        return 0.0
    tier, began, ends = window
    overlap = (min(end, ends) - max(start, began)).total_seconds()
    if overlap <= 0 or not 0 < tier <= POTION_TIERS:
        return 0.0
    value = POTION_EFFECTS[POTION_WEALTH][1][tier - 1].get("eco", {}).get("income", 0.0) * (1 + power)
    return value * overlap / (end - start).total_seconds()


def upgrade_cost(kind: str, current: int, discount: float = 0.0) -> int | None:
    """Цена следующего уровня прокачки; None — уже максимум. `discount` — скидка систем
    развития (Элита, гений бизнеса), режется потолком."""
    if current >= BUSINESS_MAX_UPGRADE:
        return None
    base = BUSINESS_LEVEL_UPGRADE_BASE_COST if kind == UPGRADE_LEVEL else BUSINESS_CAPACITY_UPGRADE_BASE_COST
    return max(1, int(base * 2**current * (1 - capped(discount, 0.6))))


def build_cost(type_: str, discount: float = 0.0, *, owned_total: int = 1) -> int:
    """Цена постройки. Защита от софтлока экономики (решение автора кода 2026-10-08): у кого нет
    ни одного бизнеса, первое кафе — бесплатно, иначе игрок без коинов и дохода застревал бы
    навсегда (старт с 500 = цена кафе, потеря всех районов в PvP)."""
    if type_ == BIZ_CAFE and owned_total == 0:
        return 0
    return max(1, int(BUSINESS_BUILD_COST[type_] * (1 - capped(discount, 0.6))))


def _capacity_per_district(capacity_level: int) -> int:
    return BUSINESS_BASE_CAPACITY + capacity_level


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- кошелёк ---


@dataclass(frozen=True, slots=True)
class WalletView:
    nh_coins: int
    pending: int  # к зачислению — уже за вычетом налога императору
    per_minute: float  # тоже за вычетом налога
    storage_full_in_seconds: int
    level: int
    capacity: int
    counts: dict[str, int]
    tax: TaxContext | None = None  # кому и сколько платит игрок


def _split(gross: int, tax: TaxContext | None, relief: float = 0.0) -> tuple[int, int]:
    """Доход игрока → (игроку, императору). Налог (10–50%) игрок теряет; пассивные +10%
    император получает сверху — у игрока они не вычитаются (пользователь 2026-10-01).
    `relief` — доля налога, от которой игрока освобождает гений бизнеса."""
    if tax is None or gross <= 0:
        return gross, 0
    taxed = gross * tax.percent // 100 if not relief else int(gross * tax.percent / 100 * (1 - capped(relief, 0.8)))
    return gross - taxed, taxed + gross * EMPEROR_PASSIVE_BONUS_PERCENT // 100


async def get_wallet(session: AsyncSession, user_id: int, *, now: datetime | None = None) -> WalletView | None:
    """Чистое чтение (без блокировок и записи) — для экрана бизнеса, профиля и Mini App."""
    now = now or _now()
    wallet = await business_repo.get_wallet(session, user_id)
    if wallet is None:
        return None
    build_ = await get_build(session, user_id)
    eco = build_.eco
    raw_counts = await business_repo.count_by_type(session, user_id)
    # Навыки позиций «утяжеляют» постройки только для дохода (дробные веса) — наружу (экран,
    # бонус спортзала/парламента) идут настоящие штуки: дробь роняла экран бизнеса Mini App.
    counts = weighted_counts(raw_counts, build_.positions)
    cap = _cap_minutes(eco)
    minutes, _ = _accrual_window(wallet.coins_accrued_at, now, cap)
    tax = await empire_repo.get_tax_context(session, user_id)
    potion = await _wealth_potion_bonus(session, user_id, wallet.coins_accrued_at, now, eco.potion_power)
    gross = _with_income(
        income_for(counts, wallet.business_level, minutes, _rng(user_id, wallet.coins_accrued_at, minutes)), eco, potion
    )
    keep = 1 - tax.percent / 100 * (1 - capped(eco.tax_relief, 0.8)) if tax else 1
    # Скорость «сейчас»: с активным зельем богатства и множителем админа — иначе экран
    # показывал бы доход без зелья, хотя начисление его учитывает (жалоба 2026-10-13).
    potion_now = await _wealth_potion_bonus(session, user_id, now - timedelta(seconds=1), now, eco.potion_power)
    from bot.services.admin.live_config import get as live_get

    rate = income_per_minute(counts, wallet.business_level) * live_get("income_multiplier")
    return WalletView(
        nh_coins=wallet.nh_coins,
        pending=_split(gross, tax, eco.tax_relief)[0],
        per_minute=rate * (1 + eco.income + potion_now) * keep,
        storage_full_in_seconds=_storage_full_in(wallet.coins_accrued_at, now, cap),
        level=wallet.business_level,
        capacity=wallet.business_capacity,
        counts=raw_counts,
        tax=tax,
    )


async def accrue(session: AsyncSession, user_id: int, *, now: datetime | None = None) -> int:
    """Зачисляет накопленный доход в `nh_coins` под `FOR UPDATE` строки игрока. НЕ коммитит
    (правило 10) — это первый шаг любой операции, меняющей доходность. Возвращает, сколько
    зачислено."""
    now = now or _now()
    wallet = await business_repo.get_wallet(session, user_id, for_update=True)
    if wallet is None:
        return 0
    build_ = await get_build(session, user_id)
    eco = build_.eco
    minutes, new_accrued_at = _accrual_window(wallet.coins_accrued_at, now, _cap_minutes(eco))
    if new_accrued_at == wallet.coins_accrued_at:
        return 0
    counts = weighted_counts(await business_repo.count_by_type(session, user_id), build_.positions)
    potion = await _wealth_potion_bonus(session, user_id, wallet.coins_accrued_at, now, eco.potion_power)
    gross = _with_income(
        income_for(counts, wallet.business_level, minutes, _rng(user_id, wallet.coins_accrued_at, minutes)), eco, potion
    )
    # Налог императору города игрока — в той же транзакции, что зачисление (правило 10).
    tax = await empire_repo.get_tax_context(session, user_id)
    # «Резервный фонд» (Бизнесмен): хранилище было полным — сбор больше.
    if build_.positions is not None and minutes >= _cap_minutes(eco) and build_.positions.get("full_storage_bonus"):
        gross = int(gross * (1 + build_.positions.get("full_storage_bonus")))
    amount, to_emperor = _split(gross, tax, eco.tax_relief)
    # Клан: владельцу и заму — по 1% сверху с дохода игрока (у игрока ничего не убывает), а
    # если игрок сам владелец/зам — забирает накопленную долю вместе со своим доходом.
    share = await clan_repo.settle_income_share(session, user_id, amount, CLAN_OWNER_SHARE, CLAN_DEPUTY_SHARE)
    await business_repo.credit_accrual(session, user_id, amount=amount + share, accrued_at=new_accrued_at)
    if to_emperor:
        await empire_repo.credit_emperor(session, tax.emperor_id, to_emperor)
    return amount + share


async def accrue_many(session: AsyncSession, user_ids: list[int]) -> None:
    """Начисление нескольким игрокам перед сменой владельца района (PvP) — строки
    блокируются в ОДНОМ порядке (по id), чтобы встречные захваты не упёрлись в дедлок.
    НЕ коммитит."""
    for user_id in sorted(set(user_ids)):
        await accrue(session, user_id)


async def collect(session: AsyncSession, user_id: int) -> int:
    """Кнопка «💰 Забрать». Коммитит сама. Двойной клик безопасен без Redis-лока: второй
    вызов ждёт `FOR UPDATE` первого и находит отметку уже сдвинутой — зачисляет ~0."""
    amount = await accrue(session, user_id)
    positions = (await get_build(session, user_id)).positions
    # «Двойная смена» (Бизнесмен): шанс удвоить собранное.
    if amount and positions is not None and random.random() < positions.get("double_collect"):
        await business_repo.add_coins(session, user_id, amount)
        amount *= 2
    if amount:
        await quest_event(session, user_id, TASK_INCOME, amount)
        await quest_event(session, user_id, TASK_COLLECT)
    await session.commit()
    return amount


# --- бонусы зданий ---


async def gym_training_bonus_percent(session: AsyncSession, user_id: int) -> int:
    return await business_repo.count_type(session, user_id, BIZ_GYM) * BUSINESS_GYM_TRAINING_BONUS_PERCENT


async def parliament_influence(session: AsyncSession, user_id: int) -> int:
    return await business_repo.count_type(session, user_id, BIZ_PARLIAMENT) * BUSINESS_PARLIAMENT_INFLUENCE


# --- экраны ---


@dataclass(frozen=True, slots=True)
class BusinessOverview:
    wallet: WalletView
    districts: list[business_repo.OwnedDistrictRow]
    capacity_per_district: int
    gym_bonus_percent: int
    parliament_influence: int
    level_cost: int | None
    capacity_cost: int | None


async def get_overview(session: AsyncSession, user_id: int) -> BusinessOverview | None:
    wallet = await get_wallet(session, user_id)
    if wallet is None:
        return None
    eco = (await get_build(session, user_id)).eco
    return BusinessOverview(
        wallet=wallet,
        districts=await business_repo.list_owned_districts(session, user_id),
        capacity_per_district=_capacity_per_district(wallet.capacity),
        gym_bonus_percent=wallet.counts.get(BIZ_GYM, 0) * BUSINESS_GYM_TRAINING_BONUS_PERCENT,
        parliament_influence=wallet.counts.get(BIZ_PARLIAMENT, 0) * BUSINESS_PARLIAMENT_INFLUENCE,
        level_cost=upgrade_cost(UPGRADE_LEVEL, wallet.level, eco.upgrade_discount),
        capacity_cost=upgrade_cost(UPGRADE_CAPACITY, wallet.capacity, eco.upgrade_discount),
    )


@dataclass(frozen=True, slots=True)
class DistrictBusinesses:
    district_id: int
    number: int
    counts: dict[str, int]
    used: int
    capacity: int
    nh_coins: int
    build_costs: dict[str, int]  # цены постройки со скидкой систем развития

    @property
    def free(self) -> int:
        return max(0, self.capacity - self.used)


async def get_district_businesses(session: AsyncSession, user_id: int, district_id: int) -> DistrictBusinesses:
    row = await get_row(session, district_id)
    if row is None or row.owner_id != user_id:
        raise NotDistrictOwnerError
    wallet = await business_repo.get_wallet(session, user_id)
    counts = await business_repo.count_by_type_on_district(session, district_id)
    discount = (await get_build(session, user_id)).eco.build_discount
    owned_total = sum((await business_repo.count_by_type(session, user_id)).values())
    return DistrictBusinesses(
        district_id=district_id,
        number=row.number,
        counts=counts,
        used=sum(counts.values()),
        capacity=_capacity_per_district(wallet.business_capacity),
        nh_coins=wallet.nh_coins,
        build_costs={t: build_cost(t, discount, owned_total=owned_total) for t in BUSINESS_TYPES},
    )


@dataclass(frozen=True, slots=True)
class DistrictsCatalog:
    counts: dict[int, dict[str, int]]  # district_id -> {тип: кол-во}
    build_costs: dict[str, int]  # цены постройки со скидкой (с правилом «первое кафе бесплатно»)


async def get_districts_catalog(session: AsyncSession, user_id: int) -> DistrictsCatalog:
    """Данные экрана «Бизнес» в Mini App: здания всех районов + каталог цен — без N+1."""
    counts = await business_repo.count_by_type_per_district(session, user_id)
    discount = (await get_build(session, user_id)).eco.build_discount
    owned_total = sum(sum(c.values()) for c in counts.values())
    return DistrictsCatalog(
        counts=counts,
        build_costs={t: build_cost(t, discount, owned_total=owned_total) for t in BUSINESS_TYPES},
    )


# --- действия ---


@dataclass(frozen=True, slots=True)
class BuildResult:
    type: str
    district_number: int
    cost: int
    collected: int


async def _cashback(session: AsyncSession, user_id: int, spent: int) -> None:
    """«Откат» (Бизнесмен): доля потраченного на стройку и прокачку возвращается. НЕ коммитит."""
    positions = (await get_build(session, user_id)).positions
    back = int(spent * min(0.3, positions.get("cashback"))) if spent and positions is not None else 0
    if back:
        await business_repo.add_coins(session, user_id, back)


async def build(session: AsyncSession, user_id: int, district_id: int, type_: str) -> BuildResult:
    """Составная операция (правило 10): начисление → лок района с проверкой владельца →
    проверка места → списание → здание → один commit. Порядок блокировок — строка
    игрока, потом район — тот же, что у PvP-захвата (`accrue_many` → `transfer_owner`)."""
    if type_ not in BUSINESS_TYPES:
        raise UnknownBusinessTypeError
    collected = await accrue(session, user_id)
    wallet = await business_repo.get_wallet(session, user_id, for_update=True)

    district = await business_repo.lock_owned_district(session, district_id, user_id)
    if district is None:
        raise NotDistrictOwnerError
    used = sum((await business_repo.count_by_type_on_district(session, district_id)).values())
    if used >= _capacity_per_district(wallet.business_capacity):
        raise NoFreeSlotError

    owned_total = sum((await business_repo.count_by_type(session, user_id)).values())
    cost = build_cost(type_, (await get_build(session, user_id)).eco.build_discount, owned_total=owned_total)
    if cost and not await business_repo.spend_coins(session, user_id, cost):
        raise NotEnoughCoinsError(cost=cost, balance=wallet.nh_coins)
    await business_repo.create(session, district_id, type_)
    await _cashback(session, user_id, cost)
    await log_activity(session, user_id, ACT_BUSINESS, LOG_BUILD.format(name=BUSINESS_NAMES[type_], number=district.number))
    await quest_event(session, user_id, TASK_BUILD)
    await session.commit()
    return BuildResult(type=type_, district_number=district.number, cost=cost, collected=collected)


@dataclass(frozen=True, slots=True)
class BuildAllResult:
    type: str
    built: int
    cost: int
    districts: int
    collected: int


async def build_all(session: AsyncSession, user_id: int, type_: str, district_id: int | None = None) -> BuildAllResult:
    """«Застроить всё»: каждое свободное место района `district_id` (или всех районов игрока)
    зданием `type_`, пока хватает NHCoin. Цена — та же `build_cost` на каждое здание (правило
    «первое кафе бесплатно» срабатывает максимум один раз — `owned_total` растёт по ходу).
    Одно списание суммой и один INSERT пачкой под теми же локами, что у `build`; один commit."""
    if type_ not in BUSINESS_TYPES:
        raise UnknownBusinessTypeError
    collected = await accrue(session, user_id)
    wallet = await business_repo.get_wallet(session, user_id, for_update=True)
    if district_id is None:
        districts = await business_repo.lock_owned_districts(session, user_id)
    else:
        one = await business_repo.lock_owned_district(session, district_id, user_id)
        if one is None:
            raise NotDistrictOwnerError
        districts = [one]
    if not districts:
        raise NotDistrictOwnerError

    capacity = _capacity_per_district(wallet.business_capacity)
    per_district = await business_repo.count_by_type_per_district(session, user_id)
    discount = (await get_build(session, user_id)).eco.build_discount
    owned_total = sum((await business_repo.count_by_type(session, user_id)).values())
    balance, total, items, touched, first_cost = wallet.nh_coins, 0, [], set(), None
    for district in districts:
        free = capacity - sum(per_district.get(district.id, {}).values())
        for _ in range(max(0, free)):
            cost = build_cost(type_, discount, owned_total=owned_total)
            first_cost = cost if first_cost is None else first_cost
            if total + cost > balance:
                break
            total += cost
            owned_total += 1
            items.append((district.id, type_))
            touched.add(district.id)
        else:
            continue
        break
    if not items:
        if first_cost is None:
            raise NoFreeSlotError
        raise NotEnoughCoinsError(cost=first_cost, balance=balance)
    if total and not await business_repo.spend_coins(session, user_id, total):
        raise NotEnoughCoinsError(cost=total, balance=balance)
    await business_repo.create_many(session, items)
    await _cashback(session, user_id, total)
    await log_activity(
        session, user_id, ACT_BUSINESS, LOG_BUILD_ALL.format(name=BUSINESS_NAMES[type_], count=len(items), districts=len(touched))
    )
    await quest_event(session, user_id, TASK_BUILD, len(items))
    await session.commit()
    return BuildAllResult(type=type_, built=len(items), cost=total, districts=len(touched), collected=collected)


@dataclass(frozen=True, slots=True)
class DemolishResult:
    removed: int
    district_number: int


async def demolish(session: AsyncSession, user_id: int, district_id: int, type_: str | None) -> DemolishResult:
    """Снести одно здание типа `type_` или всё на районе (`None`). Без возврата NHCoin
    (пользователь 2026-10-11) — освобождает место под другую постройку. Доход до сноса
    зачисляется по старому набору зданий (`accrue` первым шагом, как у стройки)."""
    if type_ is not None and type_ not in BUSINESS_TYPES:
        raise UnknownBusinessTypeError
    await accrue(session, user_id)
    await business_repo.get_wallet(session, user_id, for_update=True)
    district = await business_repo.lock_owned_district(session, district_id, user_id)
    if district is None:
        raise NotDistrictOwnerError
    removed = await business_repo.delete_on_district(session, district_id, type_)
    if not removed:
        await session.rollback()
        raise NothingToDemolishError
    await log_activity(session, user_id, ACT_BUSINESS, LOG_DEMOLISH.format(count=removed, number=district.number))
    await session.commit()
    return DemolishResult(removed=removed, district_number=district.number)


@dataclass(frozen=True, slots=True)
class UpgradeResult:
    kind: str
    new_level: int
    cost: int
    collected: int = 0  # накопленное, зачисленное в кошелёк перед прокачкой


async def upgrade(session: AsyncSession, user_id: int, kind: str) -> UpgradeResult:
    """Начисление ДО смены уровня — иначе новый множитель применился бы к доходу, уже
    накопленному по старому. Один `UPDATE` с условием на текущий уровень и баланс."""
    if kind not in (UPGRADE_LEVEL, UPGRADE_CAPACITY):
        raise UnknownBusinessTypeError
    collected = await accrue(session, user_id)
    wallet = await business_repo.get_wallet(session, user_id, for_update=True)
    current = wallet.business_level if kind == UPGRADE_LEVEL else wallet.business_capacity
    cost = upgrade_cost(kind, current, (await get_build(session, user_id)).eco.upgrade_discount)
    if cost is None:
        raise MaxUpgradeError
    if not await business_repo.bump_upgrade(session, user_id, kind=kind, current=current, cost=cost):
        raise NotEnoughCoinsError(cost=cost, balance=wallet.nh_coins)
    await _cashback(session, user_id, cost)
    await session.commit()
    return UpgradeResult(kind=kind, new_level=current + 1, cost=cost, collected=collected)


async def autobuild_for_crown(session: AsyncSession, user_id: int) -> int:
    """Перед коронацией: бесплатно занять все свободные места на районах игрока тем же набором
    зданий, что у него уже есть (нет зданий — кафе). Коронация освобождает районы, а здания уходят
    во «владения» — без этого только что захваченный последний город (десятки пустых районов)
    не давал бы ничего (пользователь 2026-10-19, AskUserQuestion: «бесплатно, тем же набором»).
    → сколько построено. НЕ коммитит."""
    wallet = await business_repo.get_wallet(session, user_id, for_update=True)
    districts = await business_repo.lock_owned_districts(session, user_id)
    if wallet is None or not districts:
        return 0
    capacity = _capacity_per_district(wallet.business_capacity)
    per_district = await business_repo.count_by_type_per_district(session, user_id)
    free = [(d.id, capacity - sum(per_district.get(d.id, {}).values())) for d in districts]
    total = sum(n for _, n in free if n > 0)
    if total <= 0:
        return 0
    mix = await business_repo.count_by_type(session, user_id) or {BIZ_CAFE: 1}
    weight = sum(mix.values())
    # Наибольший остаток: доли по типам в точности дают `total` мест.
    shares = {t: total * c / weight for t, c in mix.items()}
    plan = {t: int(v) for t, v in shares.items()}
    for t in sorted(shares, key=lambda k: shares[k] - plan[k], reverse=True)[: total - sum(plan.values())]:
        plan[t] += 1
    queue = [t for t, n in sorted(plan.items()) for _ in range(n)]
    items, i = [], 0
    for district_id, n in free:
        for _ in range(max(0, n)):
            items.append((district_id, queue[i]))
            i += 1
    await business_repo.create_many(session, items)
    return len(items)
