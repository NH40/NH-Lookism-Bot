"""Банда игрока — название, состав (9 позиций), статисты (лагеря) (сервис)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.game import GANG_NAME_MAX_LENGTH, GANG_NAME_MIN_LENGTH
from bot.db.models.gang import Gang
from bot.db.repositories.gang import create, get_by_user


class InvalidGangNameError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


class GangAlreadyExistsError(Exception):
    pass


async def get_gang(session: AsyncSession, user_id: int) -> Gang | None:
    return await get_by_user(session, user_id)


def validate_gang_name(name: str) -> str:
    """Отдельная функция (не только внутри `create_gang`) — переиспользуется хендлером
    для валидации ДО похода в БД, тот же приём, что везде в проекте (не тратить запрос
    на заведомо невалидный ввод)."""
    stripped = name.strip()
    if len(stripped) < GANG_NAME_MIN_LENGTH:
        raise InvalidGangNameError("too_short")
    if len(stripped) > GANG_NAME_MAX_LENGTH:
        raise InvalidGangNameError("too_long")
    return stripped


async def create_gang(session: AsyncSession, user_id: int, name: str) -> Gang:
    validated_name = validate_gang_name(name)
    if await get_by_user(session, user_id) is not None:
        raise GangAlreadyExistsError
    return await create(session, user_id=user_id, name=validated_name)
