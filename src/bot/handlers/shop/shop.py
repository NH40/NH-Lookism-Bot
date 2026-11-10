"""Магазин — верхнеуровневый таб (хендлеры).

Тренер Том Ли (очки мастерства за NHCoin) убран 2026-11-10: очки дают сразу за победу над Томом.
Здесь осталось только напоминание о невложенных очках.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.common import CB_MENU_SHOP
from bot.db.repositories import business as business_repo
from bot.db.repositories import mastery as mastery_repo
from bot.keyboards.shop import shop_menu
from bot.services.gang import get_gang
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.shop import FREE_POINTS, SHOP_SCREEN
from bot.utils.formatting import format_number
from bot.handlers.school import render_shop_block

router = Router(name="shop")


async def render_shop(session: AsyncSession, redis: Redis, user_id: int):
    """Экран магазина. Публичный — его же перерисовывает раздел «Обучение» (`handlers/school`)."""
    quest = await mastery_repo.get(session, user_id)
    free = quest.points_free if quest is not None else 0
    wallet = await business_repo.get_wallet(session, user_id)
    school_text, school_rows = await render_shop_block(session, redis, user_id)
    items = (FREE_POINTS.format(free=free) if free else "") + school_text
    text = SHOP_SCREEN.format(coins=format_number(wallet.nh_coins if wallet else 0), items=items)
    return text, shop_menu(has_free_points=free > 0, extra_rows=school_rows)


@router.callback_query(F.data == CB_MENU_SHOP)
async def cb_shop_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = await render_shop(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)
