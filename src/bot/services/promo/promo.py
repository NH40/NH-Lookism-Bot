"""Промокоды (сервис): создание админом, активация игроком.

Награда — словарь {код ресурса из `RESOURCES`: количество}; отрицательное — штраф, баланс может
уйти в минус (пользователь 2026-11-04: «выдал −100 000 тикетов при 3 000 — будет −97 000, дальше
набирает обычным способом»). Тратить в минусе нельзя: все списания — `WHERE баланс >= цена`.
Активация атомарна: запись активации + инкремент с проверкой лимита в
самом UPDATE, при провале инкремента — rollback (правила 1, 10).

2026-11-19: награда может быть диапазоном `ресурс:25-50` (в JSON — `[25, 50]`), число выпадает при
активации у каждого своё. Группа (`#канал`, `#рофл`) — только для порядка в админке, механика одна.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.promo import (
    PROMO_CODE_MAX_LEN,
    PROMO_LIST_LIMIT,
    PROMO_MODE_TIME,
    PROMO_MODE_USERS,
    PROMO_MODE_USES,
    PROMO_MODES,
)
from bot.constant.resource import RES_TICKETS, RESOURCES
from bot.db.models.promo import PromoCode
from bot.db.models.user import User
from bot.db.repositories import promo as promo_repo
from bot.services import resource as resource_service
from bot.services import ticket as ticket_service
from bot.services.admin import audit
from bot.services.resource.resource import _COLUMNS

_REWARD_RE = re.compile(r"^([a-z_]+):(-?\d+)(?:(?:-|\.\.)(-?\d+))?$")
_GROUP_MAX_LEN = 20  # кириллица — 2 байта: группа влезает в callback_data (64 байта)
_CODE_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_\-]+$")


class PromoError(Exception):
    pass


class PromoFormatError(PromoError):
    pass


class PromoCodeTakenError(PromoError):
    pass


class PromoNotFoundError(PromoError):
    pass


class PromoInactiveError(PromoError):
    pass


class PromoExpiredError(PromoError):
    pass


class PromoExhaustedError(PromoError):
    pass


class PromoAlreadyUsedError(PromoError):
    pass


class PromoNotAllowedError(PromoError):
    pass


@dataclass(frozen=True, slots=True)
class PromoDraft:
    code: str
    reward: dict[str, int | list[int]]
    max_uses: int | None
    expires_at: datetime | None
    allowed_usernames: list[str] | None
    group: str | None = None


def roll(value: int | list[int]) -> int:
    """Количество из награды: число как есть, диапазон `[от, до]` — случайное внутри."""
    if isinstance(value, list):
        return random.randint(int(value[0]), int(value[1]))
    return int(value)


def reward_sign(value: int | list[int]) -> int:
    lo, hi = (value[0], value[1]) if isinstance(value, list) else (value, value)
    return 1 if lo + hi > 0 else -1


def reward_label(code: str, value: int | list[int]) -> str:
    """«+25–50 🎟», «−100 🪙» — для админки и списков."""
    from bot.texts.resource import amount_label
    from bot.utils.formatting import format_number

    sign = "+" if reward_sign(value) > 0 else "−"
    if isinstance(value, list):
        lo, hi = sorted((abs(int(value[0])), abs(int(value[1]))))
        return f"{sign}{format_number(lo)}–{amount_label(code, hi)}"
    return f"{sign}{amount_label(code, abs(int(value)))}"


def parse_create(line: str) -> PromoDraft:
    """`КОД [#группа] [uses|time|users] ПАРАМ РЕСУРС:КОЛ|РЕСУРС:ОТ-ДО ...` → черновик. PromoFormatError при ошибке."""
    tokens = line.split()
    if len(tokens) < 2:
        raise PromoFormatError
    code = tokens[0].upper()
    if len(code) > PROMO_CODE_MAX_LEN or not _CODE_RE.match(code):
        raise PromoFormatError
    rest = tokens[1:]
    group = None
    if rest[0].startswith("#"):
        group = rest[0][1:].lower()
        if not group or len(group) > _GROUP_MAX_LEN or not _CODE_RE.match(group) or len(rest) < 2:
            raise PromoFormatError
        rest = rest[1:]
    max_uses = expires_at = allowed = None
    if rest[0].lower() in PROMO_MODES:
        if len(rest) < 3:
            raise PromoFormatError
        mode, param, rest = rest[0].lower(), rest[1], rest[2:]
        if mode == PROMO_MODE_USES:
            if not param.isdigit() or int(param) < 1:
                raise PromoFormatError
            max_uses = int(param)
        elif mode == PROMO_MODE_TIME:
            if not param.isdigit() or int(param) < 1:
                raise PromoFormatError
            expires_at = datetime.now(timezone.utc) + timedelta(hours=int(param))
        elif mode == PROMO_MODE_USERS:
            allowed = [u.lstrip("@").lower() for u in param.split(",") if u.lstrip("@")]
            if not allowed:
                raise PromoFormatError
            max_uses = len(allowed)
    reward: dict[str, int | list[int]] = {}
    for token in rest:
        match = _REWARD_RE.match(token.lower())
        if not match or match.group(1) not in RESOURCES:
            raise PromoFormatError
        res, first = match.group(1), int(match.group(2))
        if match.group(3) is not None:  # диапазон: одним токеном на ресурс, не складывается с другими
            lo, hi = sorted((first, int(match.group(3))))
            if res in reward or (lo == 0 and hi == 0) or (lo < 0 < hi):
                raise PromoFormatError
            reward[res] = [lo, hi] if lo != hi else lo
            continue
        if first == 0 or isinstance(reward.get(res), list):
            raise PromoFormatError
        reward[res] = reward.get(res, 0) + first
    if not reward:
        raise PromoFormatError
    return PromoDraft(code, reward, max_uses, expires_at, allowed, group)


async def create(session: AsyncSession, admin_id: int, draft: PromoDraft) -> PromoCode:
    if await promo_repo.get_by_code(session, draft.code) is not None:
        raise PromoCodeTakenError
    promo = await promo_repo.add(
        session, code=draft.code, reward=draft.reward, max_uses=draft.max_uses,
        expires_at=draft.expires_at, allowed_usernames=draft.allowed_usernames, created_by=admin_id, group_name=draft.group,
    )
    await audit.log(session, admin_id, "promo_create", None, {"code": promo.code, "reward": promo.reward, "group": promo.group_name})
    await session.commit()
    return promo


def is_alive(promo: PromoCode, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if not promo.is_active:
        return False
    if promo.expires_at is not None and promo.expires_at <= now:
        return False
    return promo.max_uses is None or promo.used_count < promo.max_uses


async def list_recent(session: AsyncSession, group: str | None = None) -> list[PromoCode]:
    return await promo_repo.list_recent(session, PROMO_LIST_LIMIT, group)


async def groups(session: AsyncSession) -> list[tuple[str, int]]:
    return await promo_repo.groups(session)


async def get(session: AsyncSession, promo_id: int) -> PromoCode | None:
    return await promo_repo.get(session, promo_id)


async def set_active(session: AsyncSession, admin_id: int, promo_id: int, active: bool) -> bool:
    if not await promo_repo.set_active(session, promo_id, active):
        return False
    await audit.log(session, admin_id, "promo_on" if active else "promo_off", None, {"promo_id": promo_id})
    await session.commit()
    return True


async def delete(session: AsyncSession, admin_id: int, promo_id: int) -> bool:
    promo = await promo_repo.get(session, promo_id)
    if promo is None:
        return False
    await audit.log(session, admin_id, "promo_delete", None, {"code": promo.code})
    await promo_repo.delete_promo(session, promo_id)
    await session.commit()
    return True


async def _apply_delta(session: AsyncSession, user_id: int, code: str, delta: int) -> None:
    """Начислить или снять (можно уйти в минус). НЕ коммитит."""
    if delta > 0:
        await resource_service.grant(session, user_id, code, delta)
    elif code == RES_TICKETS:
        await ticket_service.spend(session, user_id, 0)  # зафиксировать реген до штрафа
        await ticket_service.refund(session, user_id, delta)
    else:
        column = _COLUMNS[code]
        await session.execute(update(User).where(User.id == user_id).values({column: column + delta}))


async def redeem(session: AsyncSession, user: User, raw_code: str) -> dict[str, int]:
    """Активировать код игроком. → выданная награда. Коммитит сама (верхнеуровневая операция)."""
    promo = await promo_repo.get_by_code(session, raw_code.strip().upper())
    if promo is None:
        raise PromoNotFoundError
    if not promo.is_active:
        raise PromoInactiveError
    if promo.expires_at is not None and promo.expires_at <= datetime.now(timezone.utc):
        raise PromoExpiredError
    if promo.allowed_usernames is not None and (user.username or "").lower() not in promo.allowed_usernames:
        raise PromoNotAllowedError
    promo_id = promo.id
    reward = {code: roll(value) for code, value in promo.reward.items()}  # диапазон — своё число каждому
    if not await promo_repo.insert_redemption(session, promo_id, user.id):
        await session.rollback()
        raise PromoAlreadyUsedError
    if not await promo_repo.increment_used(session, promo_id):
        await session.rollback()
        raise PromoExhaustedError
    for code, amount in reward.items():
        await _apply_delta(session, user.id, code, int(amount))
    await session.commit()
    return reward
