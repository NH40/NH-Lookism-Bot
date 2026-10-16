"""Удаление банды — полный сброс прогресса (сервис).

raw-notes «Фазы»: «в профиле в самом низу кнопка удаления банды, которая фулл сбрасывает
прогресс, позволяет выбрать другую страну». Пользователь 2026-10-01: сбрасывается всё,
КРОМЕ потенциала, пробуждения, родословной и таланта (последних трёх пока нет в коде) —
иначе удаление банды стало бы бесплатным перебросом потенциала, который меняется только при
перерождении. NHCoin и тикеты — стартовые, как у нового игрока.

Подтверждение — в два шага с флагом в Redis (`EX` 30 с): экран подтверждения ставит флаг,
кнопка «Да» атомарно его забирает (`GETDEL`) — повтор/устаревшая кнопка не сработают.
"""
from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import gang_delete_confirm
from bot.config.game import GANG_DELETE_CONFIRM_SECONDS, NH_COINS_STARTING, TICKET_STARTING
from bot.db.repositories.gang import reset_player
from bot.services.bloodline import apply_effects as apply_bloodline_effects
from bot.services.donate import apply_all as apply_donate


class ConfirmExpiredError(Exception):
    pass


async def request_delete(redis: Redis, user_id: int) -> int:
    await redis.set(gang_delete_confirm(user_id), "1", ex=GANG_DELETE_CONFIRM_SECONDS)
    return GANG_DELETE_CONFIRM_SECONDS


async def confirm_delete(session: AsyncSession, redis: Redis, user_id: int) -> None:
    if not await redis.getdel(gang_delete_confirm(user_id)):
        raise ConfirmExpiredError
    await reset_player(session, user_id, nh_coins=NH_COINS_STARTING, tickets=TICKET_STARTING)
    # Родословная остаётся — её пол характеристик (Ким Гапрен) и выданное ею держатся и после сброса.
    await apply_bloodline_effects(session, user_id)
    await apply_donate(session, user_id)  # купленные за донат техники/гении/уровни — обратно
    await session.commit()
