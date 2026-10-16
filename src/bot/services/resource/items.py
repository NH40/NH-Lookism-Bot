"""Предмет — ресурс или отряд статистов (`constant/resource.ITEM_*`): одна точка «забрать /
отдать» для биржи (лоты, аукционы, обмен). НЕ коммитят — шаги чужих транзакций."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.resource import ITEM_RESOURCE, ITEM_STATIST, RESOURCES
from bot.services.resource.resource import grant, spend
from bot.services.resource.statists import StatistKey, give_statists, take_statists


class InvalidItemError(Exception):
    pass


def check_item(kind: str, code: str, amount: int) -> None:
    if amount <= 0:
        raise InvalidItemError
    if kind == ITEM_RESOURCE:
        if code not in RESOURCES:
            raise InvalidItemError
    elif kind == ITEM_STATIST:
        try:
            StatistKey.decode(code)
        except ValueError as exc:
            raise InvalidItemError from exc
    else:
        raise InvalidItemError


async def take_item(session: AsyncSession, user_id: int, kind: str, code: str, amount: int) -> bool:
    check_item(kind, code, amount)
    if kind == ITEM_RESOURCE:
        return await spend(session, user_id, code, amount)
    return await take_statists(session, user_id, StatistKey.decode(code), amount)


async def give_item(session: AsyncSession, user_id: int, kind: str, code: str, amount: int) -> None:
    if amount <= 0:
        return
    if kind == ITEM_RESOURCE:
        await grant(session, user_id, code, amount)
    else:
        await give_statists(session, user_id, StatistKey.decode(code), amount)
