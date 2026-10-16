"""Абсолютные карты — действующие перки игрока (сервис, пользователь 2026-10-16).

Абсолют действует, пока у игрока есть хотя бы одна копия (в любом лагере): он не воюет и не
гибнет (`services/district/army.load_camp` его не берёт). Стилист добавляет выбранный перк
другого абсолюта. Ариан атакующего блокирует абсолюты цели (`users.absolute_blocked_until`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.absolute import ABS_STYLIST, ABSOLUTES, STYLIST_CHOICES
from bot.db.models.card_stack import CardStack
from bot.db.models.user import User


async def owned(session: AsyncSession, user_id: int) -> frozenset[str]:
    """Абсолюты, которыми игрок владеет (без учёта блока Ариана), + перк Стилиста."""
    codes = set(await session.scalars(
        select(CardStack.card_code).where(CardStack.user_id == user_id, CardStack.card_code.in_(ABSOLUTES), CardStack.quantity > 0)
    ))
    if ABS_STYLIST in codes:
        pick = await session.scalar(select(User.absolute_style_pick).where(User.id == user_id))
        if pick in STYLIST_CHOICES:
            codes.add(pick)
    return frozenset(codes)


async def active(session: AsyncSession, user_id: int) -> frozenset[str]:
    """Действующие сейчас: владение минус блок Ариана."""
    blocked = await session.scalar(select(User.absolute_blocked_until).where(User.id == user_id))
    if blocked is not None and blocked > datetime.now(timezone.utc):
        return frozenset()
    return await owned(session, user_id)


class StylistError(Exception):
    """Нет Стилиста или перк не из списка."""


async def set_style_pick(session: AsyncSession, user_id: int, code: str) -> None:
    """Стилист выбирает перк абсолюта. Коммитит."""
    from sqlalchemy import update

    if code not in STYLIST_CHOICES or ABS_STYLIST not in await owned(session, user_id):
        raise StylistError
    await session.execute(update(User).where(User.id == user_id).values(absolute_style_pick=code))
    await session.commit()


async def style_pick(session: AsyncSession, user_id: int) -> str | None:
    return await session.scalar(select(User.absolute_style_pick).where(User.id == user_id))
