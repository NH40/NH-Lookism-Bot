"""Абсолют Архангел — раз в час доля часового дохода игрока (фоновый проход, сервис).

Проход каждые `ARKHANGEL_SWEEP_SECONDS`; выплата одному игроку — не чаще раза в час: Redis-ключ
`SET NX EX` (переживает перезапуск бота, двойной выплаты нет). Владельцы — у кого есть копия
Архангела или Стилист с выбранным перком Архангела; блок Ариана — пропуск.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.absolute import ARKHANGEL_INCOME_SHARE, ARKHANGEL_INTERVAL_SECONDS
from bot.constant.absolute import ABS_ARKHANGEL, ABS_STYLIST
from bot.constant.settings import NOTIFY_ARKHANGEL
from bot.db.models.card_stack import CardStack
from bot.db.models.user import User
from bot.db.repositories import business as business_repo
from bot.services.absolute.absolute import active
from bot.texts.absolute import PUSH_ARKHANGEL
from bot.utils.formatting import format_number

log = logging.getLogger(__name__)
ARKHANGEL_SWEEP_SECONDS = 5 * 60


def _key(user_id: int) -> str:
    return f"absolute:arkhangel:{user_id}"


async def holders(session: AsyncSession) -> list[int]:
    arkh = select(CardStack.user_id).where(CardStack.card_code == ABS_ARKHANGEL, CardStack.quantity > 0)
    stylist = select(CardStack.user_id).where(CardStack.card_code == ABS_STYLIST, CardStack.quantity > 0)
    rows = await session.scalars(
        select(User.id).where(or_(User.id.in_(arkh), User.id.in_(stylist) & (User.absolute_style_pick == ABS_ARKHANGEL)))
    )
    return list(rows)


async def sweep(bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> int:
    from bot.services.business import get_wallet
    from bot.services.settings import notify_player

    paid = 0
    async with session_factory() as session:
        ids = await holders(session)
    for user_id in ids:
        if not await redis.set(_key(user_id), "1", nx=True, ex=ARKHANGEL_INTERVAL_SECONDS):
            continue
        try:
            async with session_factory() as session:
                if ABS_ARKHANGEL not in await active(session, user_id):
                    continue
                wallet = await get_wallet(session, user_id)
                amount = int((wallet.per_minute if wallet else 0) * 60 * ARKHANGEL_INCOME_SHARE)
                if amount <= 0:
                    continue
                await business_repo.add_coins(session, user_id, amount)
                await session.commit()
                await notify_player(bot, session, user_id, NOTIFY_ARKHANGEL, PUSH_ARKHANGEL.format(
                    amount=format_number(amount), share=f"{ARKHANGEL_INCOME_SHARE:.0%}",
                ))
                paid += 1
        except Exception:
            log.exception("Arkhangel payout failed for %s", user_id)
    return paid
