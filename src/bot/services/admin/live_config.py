"""Настройки на лету: реестр ключей, кэш в памяти (загружается при старте), запись в `game_settings`.

`get(key)` — синхронный: переопределение (если не истекло) или значение по умолчанию из config.
Пишут и бот, и API Mini App (админка в Mini App, 2026-10-17) — у каждого процесса свой кэш,
поэтому оба перечитывают таблицу раз в `LIVE_CONFIG_REFRESH_SECONDS` (`refresh_loop`): правка из
другого процесса доходит с этой задержкой, свой процесс видит её сразу.

Константы из каталога (`config/admin/live_catalog`, пользователь 2026-11-04: «чуть ли не все
константы менять из игры») код читает как обычные имена модуля, не через `get()`. Поэтому новое
значение записывается прямо в модули, где это имя импортировано (`_apply_constants`) — править
сотни мест использования не пришлось. Значения, вшитые при импорте (f-строки описаний — `TEXT_FROZEN`),
так не меняются: логика новая, текст старый."""
from __future__ import annotations

import hashlib
import importlib
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.admin.live_catalog import SCALARS, SECTIONS, TABLES, TEXT_FROZEN
from bot.constant.admin.live_config import (
    AUDIT_CONFIG_RESET,
    AUDIT_CONFIG_SET,
    KEY_BODY_PRICE,
    KEY_BP_PRICE,
    KEY_CD_BATTLE_PREFIX,
    KEY_CD_COUNTRY_SWAP,
    KEY_CD_EMPIRE_ANNOUNCE,
    KEY_CD_EMPIRE_WAR,
    KEY_CD_EXTRAS,
    KEY_CD_PERSONAL,
    KEY_CD_RECRUIT,
    KEY_CD_SABOTAGE,
    KEY_CD_SCHOOL,
    KEY_CD_SWAP_GENIUS,
    KEY_CD_SWAP_PATH,
    KEY_CD_SWAP_TECH,
    KEY_BP_XP_MULT,
    KEY_INCOME_MULT,
    KEY_START_COINS,
    KEY_START_TICKETS,
)
from bot.db.models.admin import GameSetting
from bot.services.admin import audit

log = logging.getLogger(__name__)


SECTION_GENERAL = "general"
SECTION_COOLDOWN = "cooldown"
SECTION_SHIELD = "shield"
SECTION_CHANGED = "_changed"  # не раздел каталога: всё, что сейчас изменено


@dataclass(frozen=True)
class LiveKey:
    key: str
    title: str
    type: type  # int | float
    min: float
    max: float
    default: Callable[[], float]
    expiring: bool = False  # множители — с необязательным сроком
    section: str = SECTION_GENERAL
    const: str = ""  # имя константы модулей (каталог); пусто — читается через `get()`
    table_key: object = None  # ключ или индекс значения внутри таблицы
    text_frozen: bool = False  # число ещё вшито в описание для игрока


def _d_bp_price() -> int:
    from bot.config.battle_pass import BP_PREMIUM_PRICE

    return BP_PREMIUM_PRICE


def _d_body_price() -> int:
    from bot.config.donate import SECOND_BODY_PRICE

    return SECOND_BODY_PRICE


def _d_coins() -> int:
    from bot.config.game import NH_COINS_STARTING

    return NH_COINS_STARTING


def _d_tickets() -> int:
    from bot.config.game import TICKET_STARTING

    return TICKET_STARTING


def _cfg_minutes(module: str, name: str, key=None):
    """Значение по умолчанию — константа конфига (секунды) в минутах; `key` — для словарей по фазе."""
    def read() -> int:
        import importlib

        value = getattr(importlib.import_module(module), name)
        return int((value[key] if key is not None else value) // 60)

    return read


_PHASE_TITLES = {"gang": "банда", "circle": "круг", "fist": "кулак"}
_MINUTES_MAX = 7 * 24 * 60

_COOLDOWN_KEYS = (
    *(
        LiveKey(f"{KEY_CD_BATTLE_PREFIX}{phase}", f"КД боя ({title}), мин", int, 0, _MINUTES_MAX,
                _cfg_minutes("bot.config.game", "BATTLE_COOLDOWN_SECONDS", phase), section=SECTION_COOLDOWN)
        for phase, title in _PHASE_TITLES.items()
    ),
    LiveKey(KEY_CD_PERSONAL, "КД личной тренировки, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.game", "PERSONAL_TRAINING_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_EXTRAS, "КД тренировки статистов, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.game", "EXTRA_TRAINING_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_RECRUIT, "КД вербовки статистов, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.game", "RECRUIT_EXTRA_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_SCHOOL, "КД занятия в школе, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.school", "SCHOOL_LESSON_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_SABOTAGE, "КД саботажа (на действие), мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.empire", "SABOTAGE_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_COUNTRY_SWAP, "КД смены страны (переезд), мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.country", "COUNTRY_SWAP_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_EMPIRE_ANNOUNCE, "КД объявления императора игрокам, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.empire", "EMPIRE_ANNOUNCE_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_EMPIRE_WAR, "КД объявления войны императоров, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.empire", "EMPIRE_WAR_COOLDOWN_SECONDS"), section=SECTION_SHIELD),
    LiveKey(KEY_CD_SWAP_PATH, "КД смены пути, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.unique_path", "PATH_SWAP_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_SWAP_TECH, "КД смены техники, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.unique_technique", "TECHNIQUE_SWAP_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
    LiveKey(KEY_CD_SWAP_GENIUS, "КД смены гениальности, мин", int, 0, _MINUTES_MAX, _cfg_minutes("bot.config.genius", "GENIUS_SWAP_COOLDOWN_SECONDS"), section=SECTION_COOLDOWN),
)


# Границы, которые нельзя вывести из значения: ноль здесь ломает формулу или отключает механику.
_BOUNDS: dict[str, tuple[float, float]] = {
    "EXTRA_TRAINING_STAGE1_POWER_MULTIPLIER": (1.0, 1.5),
    "EXTRA_TRAINING_LEVEL_CAP_BASE": (1, 1000),
    "EXTRA_TRAINING_LEVEL_CAP_STEP": (0, 1000),
    "EMPIRE_WAR_BIG_GAP_RATIO": (1.1, 100.0),
    "BLACKJACK_DEALER_STAND": (1, 21),
    "SLOTS_RIG_CHANCE": (0.0, 1.0),
    "BLACKJACK_RIG_CHANCE": (0.0, 1.0),
    "MASTERY_UNLOCK_RANK_INDEX": (0, 52),
}
_ZERO_OK = re.compile(r"PERCENT|CHANCE|BONUS|SHARE|DISCOUNT|REFUND|MIN$|FLOOR|SHIELD|_PP$|COMMISSION|RAKE|TIER")
_INT_MAX = 10**15


def _bounds(name: str, value: float) -> tuple[float, float]:
    """Диапазон ввода: защита от опечатки, а не игровое ограничение."""
    if name in _BOUNDS:
        return _BOUNDS[name]
    if isinstance(value, float):
        return 0.0, max(10.0, value * 100)
    low = 0 if value <= 0 or _ZERO_OK.search(name) else 1
    if "PERCENT" in name or "CHANCE" in name:
        return low, max(100, value * 10)
    return low, min(max(value * 1000, 1_000_000), _INT_MAX)


def _catalog_keys() -> list[LiveKey]:
    keys = []
    for name, (section, module, title) in SCALARS.items():
        value = getattr(importlib.import_module(module), name)
        low, high = _bounds(name, value)
        keys.append(LiveKey(name, title, type(value), low, high, (lambda v=value: v), section=section, const=name, text_frozen=name in TEXT_FROZEN))
    for name, (section, module, title) in TABLES.items():
        table = getattr(importlib.import_module(module), name)
        for idx, value in (table.items() if isinstance(table, dict) else enumerate(table)):
            label = idx + 1 if isinstance(idx, int) and not isinstance(table, dict) else idx
            low, high = _bounds(name, value)
            keys.append(LiveKey(f"{name}|{idx}"[:64], f"{title} {label}", type(value), low, high, (lambda v=value: v), section=section, const=name, table_key=idx))
    return keys


LIVE_KEYS: dict[str, LiveKey] = {
    k.key: k
    for k in (
        LiveKey(KEY_BP_XP_MULT, "Множитель опыта пасса", float, 0.1, 10.0, lambda: 1.0, True),
        LiveKey(KEY_INCOME_MULT, "Множитель дохода бизнеса", float, 0.1, 10.0, lambda: 1.0, True),
        LiveKey(KEY_START_COINS, "Стартовые NHCoin новичка", int, 0, 10_000_000, _d_coins),
        LiveKey(KEY_START_TICKETS, "Стартовые тикеты новичка", int, 0, 10_000, _d_tickets),
        LiveKey(KEY_BP_PRICE, "Цена премиум-пасса (донат-коины)", int, 0, 1_000_000, _d_bp_price),
        LiveKey(KEY_BODY_PRICE, "Цена второго тела (донат-коины)", int, 0, 10_000_000, _d_body_price),
        *_COOLDOWN_KEYS,
        *_catalog_keys(),
    )
}
_BY_SID: dict[str, str] = {}

_cache: dict[str, tuple[float, datetime | None]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: dict) -> tuple[float, datetime | None] | None:
    try:
        until = raw.get("until")
        return raw["value"], (datetime.fromisoformat(until) if until else None)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


async def refresh_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Фоновое перечитывание переопределений (бот и API — разные процессы, см. докстринг)."""
    import asyncio

    from bot.config.admin import LIVE_CONFIG_REFRESH_SECONDS

    while True:
        await asyncio.sleep(LIVE_CONFIG_REFRESH_SECONDS)
        try:
            await load(session_factory, quiet=True)
        except Exception:  # noqa: BLE001 — БД недоступна: попробуем в следующий раз
            log.exception("Live config refresh failed")


async def load(session_factory: async_sessionmaker[AsyncSession], *, quiet: bool = False) -> None:
    async with session_factory() as session:
        rows = (await session.execute(select(GameSetting).where(GameSetting.key.in_(list(LIVE_KEYS))))).scalars().all()
    _cache.clear()
    for row in rows:
        parsed = _parse(row.value)
        if parsed:
            _cache[row.key] = parsed
    _apply_constants()
    if not quiet:
        log.info("Live config loaded: %d overrides", len(_cache))


_applied: dict[str, float] = {}


def _propagate(name: str, value) -> None:
    """Записать значение константы во все модули игры, где импортировано это имя."""
    for mod_name, module in list(sys.modules.items()):
        if module is not None and mod_name.split(".")[0] in ("bot", "api") and name in vars(module):
            setattr(module, name, value)


def _apply_constants() -> None:
    """Привести константы модулей к действующим значениям (правка, сброс, чужой процесс)."""
    for key, spec in LIVE_KEYS.items():
        if not spec.const:
            continue
        want = get(key)
        if _applied.get(key, spec.default()) == want:
            continue
        _applied[key] = want
        if spec.table_key is None:
            _propagate(spec.const, want)
            continue
        table = getattr(importlib.import_module(SCALAR_TABLE_MODULE[spec.const]), spec.const)
        if isinstance(table, dict):
            table[spec.table_key] = want  # один объект на все модули
        else:
            _propagate(spec.const, tuple(want if i == spec.table_key else v for i, v in enumerate(table)))


SCALAR_TABLE_MODULE = {name: module for name, (_, module, _) in TABLES.items()}


def sid(key: str) -> str:
    """Короткий id ключа для callback_data (предел Telegram — 64 байта)."""
    return hashlib.md5(key.encode()).hexdigest()[:10]


def by_sid(short: str) -> str | None:
    if not _BY_SID:
        _BY_SID.update({sid(k): k for k in LIVE_KEYS})
    return _BY_SID.get(short)


def sections() -> list[tuple[str, str, int]]:
    """(код, название, сколько настроек) — разделы каталога в порядке показа."""
    counts: dict[str, int] = {}
    for spec in LIVE_KEYS.values():
        counts[spec.section] = counts.get(spec.section, 0) + 1
    return [(code, title, counts[code]) for code, title in SECTIONS.items() if code in counts]


def keys_of(section: str) -> list[str]:
    if section == SECTION_CHANGED:
        return [k for k in LIVE_KEYS if override(k) is not None]
    return [k for k, spec in LIVE_KEYS.items() if spec.section == section]


_DURATION_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(с|сек|s|м|мин|m|ч|h|д|d)$", re.IGNORECASE)
_UNIT_SECONDS = {"с": 1, "сек": 1, "s": 1, "м": 60, "мин": 60, "m": 60, "ч": 3600, "h": 3600, "д": 86400, "d": 86400}


def _key_unit(key: str) -> int | None:
    """Секунд в единице хранения ключа-длительности (сек / мин / ч), иначе None."""
    if key.endswith("_SECONDS"):
        return 1
    if key.endswith("_MINUTES"):
        return 60
    if key.endswith("_HOURS"):
        return 3600
    return None


def human(key: str, value: float) -> str:
    """Значение для экрана: у длительностей — ещё и понятным временем."""
    text = f"{value:g}" if isinstance(value, float) else str(value)
    unit = _key_unit(key)
    if unit is None or not value:
        return text
    seconds = value * unit
    for size, name in ((86400, "д"), (3600, "ч"), (60, "мин")):
        if seconds >= size:
            return f"{text} ({seconds / size:g} {name})"
    return text


def override(key: str) -> tuple[float, datetime | None] | None:
    """Действующее переопределение (не истёкшее) или None."""
    entry = _cache.get(key)
    if entry is None or (entry[1] is not None and entry[1] <= _now()):
        return None
    return entry


def get(key: str):
    entry = override(key)
    spec = LIVE_KEYS[key]
    return spec.type(entry[0]) if entry else spec.default()


def validate(key: str, raw: str) -> float | None:
    spec = LIVE_KEYS[key]
    text = raw.strip().replace(",", ".") if spec.type is float else raw.strip()
    unit = _key_unit(key)
    match = _DURATION_RE.match(raw.strip()) if unit else None
    if match:  # «12ч», «30м», «1д» для длительностей
        seconds = float(match.group(1).replace(",", ".")) * _UNIT_SECONDS[match.group(2).lower()]
        text = str(round(seconds / unit))
    try:
        value = spec.type(text)
    except ValueError:
        return None
    return value if spec.min <= value <= spec.max else None


async def set_value(session: AsyncSession, admin_id: int, key: str, value: float, hours: int = 0) -> None:
    """Записать переопределение (hours=0 — навсегда). Коммитит."""
    until = _now() + timedelta(hours=hours) if hours else None
    payload = {"value": value, "until": until.isoformat() if until else None}
    stmt = insert(GameSetting).values(key=key, value=payload, updated_by=admin_id)
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["key"], set_={"value": payload, "updated_by": admin_id})
    )
    await audit.log(session, admin_id, AUDIT_CONFIG_SET, None, {"key": key, "value": value, "hours": hours})
    await session.commit()
    _cache[key] = (value, until)
    _apply_constants()


async def reset(session: AsyncSession, admin_id: int, key: str) -> None:
    await session.execute(delete(GameSetting).where(GameSetting.key == key))
    await audit.log(session, admin_id, AUDIT_CONFIG_RESET, None, {"key": key})
    await session.commit()
    _cache.pop(key, None)
    _apply_constants()


def cooldown_seconds(key: str) -> int:
    """КД из настроек на лету (ключи `KEY_CD_*` хранятся в минутах) → секунды."""
    return int(get(key)) * 60


def battle_cooldown_seconds(phase: str) -> int:
    """КД боя по фазе игрока (банда/круг/кулак) — секунды."""
    return cooldown_seconds(f"{KEY_CD_BATTLE_PREFIX}{phase}")
