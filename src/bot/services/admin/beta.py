"""Бета-режим — доступ к боту по кодовому слову (сервис).

Срочный запрос пользователя 2026-09-30: пока бета включена, все игроки, кроме админов,
перед любым действием в боте вводят кодовое слово, которое спрашивают у админа. Выключили
и снова включили — допуски у всех сбрасываются, нужен новый код.

**Хранение — только Redis**, как флаг техрежима: это переключаемый режим доступа, не
игровые данные, и проверяется на КАЖДОМ апдейте (`middlewares/beta_gate`) — поход в
Postgres на каждый апдейт 30k игроков ради него был бы лишним (правило 4). Цена: если
Redis потеряет данные, бета выключится и тестерам придётся заново ввести код — приемлемо.

**Эпоха.** `beta:state` = `{эпоха}:{код}`, эпоха — случайная при каждом включении;
допущенные — множество `beta:allowed:{эпоха}`. Выключение удаляет и состояние, и
множество; новое включение — новая эпоха и пустое множество, старые допуски физически не
могут сработать. Смена кода (без выключения) эпоху не меняет — уже допущенные остаются.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum

from redis.asyncio import Redis

from bot.cache.keys import beta_allowed, beta_attempts, beta_state
from bot.config.admin import (
    BETA_ATTEMPTS_WINDOW_SECONDS,
    BETA_CODE_MAX_LENGTH,
    BETA_CODE_MIN_LENGTH,
    BETA_GENERATED_CODE_LENGTH,
    BETA_MAX_ATTEMPTS,
)

# Без похожих символов (0/o, 1/l/i) — код диктуют голосом и перепечатывают руками.
_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


class InvalidBetaCodeError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason  # "too_short" | "too_long"


@dataclass(frozen=True, slots=True)
class BetaState:
    epoch: str
    code: str


class EntryResult(Enum):
    GRANTED = "granted"
    WRONG = "wrong"
    LOCKED = "locked"


def normalize_code(text: str) -> str:
    """Регистр и лишние пробелы не важны: «Лукизм  2» == «лукизм 2»."""
    return " ".join(text.split()).casefold()


def validate_code(text: str) -> str:
    code = normalize_code(text)
    if len(code) < BETA_CODE_MIN_LENGTH:
        raise InvalidBetaCodeError("too_short")
    if len(code) > BETA_CODE_MAX_LENGTH:
        raise InvalidBetaCodeError("too_long")
    return code


def generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(BETA_GENERATED_CODE_LENGTH))


def _parse(raw: str | None) -> BetaState | None:
    if not raw:
        return None
    epoch, code = raw.split(":", 1)
    return BetaState(epoch=epoch, code=code)


async def get_state(redis: Redis) -> BetaState | None:
    return _parse(await redis.get(beta_state()))


async def enable(redis: Redis, code: str) -> BetaState | None:
    """Включает бету с новой эпохой. `SET NX` — два админа, включившие одновременно, не
    перетрут друг другу код: второй получит None (бета уже включена)."""
    state = BetaState(epoch=secrets.token_hex(4), code=validate_code(code))
    if not await redis.set(beta_state(), f"{state.epoch}:{state.code}", nx=True):
        return None
    return state


async def change_code(redis: Redis, code: str) -> BetaState | None:
    """Новый код в той же эпохе — уже допущенные остаются. `SET XX` — если бету успели
    выключить, код не "включит" её обратно; вернёт None."""
    current = await get_state(redis)
    if current is None:
        return None
    state = BetaState(epoch=current.epoch, code=validate_code(code))
    if not await redis.set(beta_state(), f"{state.epoch}:{state.code}", xx=True):
        return None
    return state


async def disable(redis: Redis) -> int | None:
    """Выключает бету и сбрасывает ВСЕ допуски. Возвращает, сколько игроков было допущено
    (None — бета и так выключена). `GETDEL` — атомарно, двойной клик не посчитает дважды."""
    state = _parse(await redis.getdel(beta_state()))
    if state is None:
        return None
    allowed = await redis.scard(beta_allowed(state.epoch))
    await redis.delete(beta_allowed(state.epoch))
    return allowed


async def allowed_count(redis: Redis, state: BetaState) -> int:
    return await redis.scard(beta_allowed(state.epoch))


async def is_allowed(redis: Redis, state: BetaState, user_id: int) -> bool:
    return bool(await redis.sismember(beta_allowed(state.epoch), str(user_id)))


async def try_enter(redis: Redis, state: BetaState, user_id: int, text: str) -> EntryResult:
    """Проверка кода игроком. Неверные попытки считаются в окне с TTL — после
    `BETA_MAX_ATTEMPTS` ввод блокируется до конца окна (не перебрать код ботом)."""
    attempts_key = beta_attempts(state.epoch, user_id)
    attempts = int(await redis.get(attempts_key) or 0)
    if attempts >= BETA_MAX_ATTEMPTS:
        return EntryResult.LOCKED
    if normalize_code(text) == state.code:
        await redis.sadd(beta_allowed(state.epoch), str(user_id))
        await redis.delete(attempts_key)
        return EntryResult.GRANTED
    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        await redis.expire(attempts_key, BETA_ATTEMPTS_WINDOW_SECONDS)
    return EntryResult.LOCKED if attempts >= BETA_MAX_ATTEMPTS else EntryResult.WRONG
