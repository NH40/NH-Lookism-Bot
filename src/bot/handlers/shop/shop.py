"""Магазин — верхнеуровневый таб (хендлеры).

Тренер Том Ли (очки мастерства за NHCoin) убран 2026-11-10: очки дают сразу за победу над Томом.
Здесь — напоминание о невложенных очках и тикеты за NHCoin (2026-11-19).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.common import CB_MENU_SHOP
from bot.constant.shop import CB_SHOP_TICKETS_PREFIX
from bot.db.repositories import business as business_repo
from bot.db.repositories import mastery as mastery_repo
from bot.keyboards.shop import shop_menu
from bot.services import shop as shop_svc
from bot.services.gang import get_gang
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.shop import FREE_POINTS, SHOP_BUSY, SHOP_SCREEN, TICKETS_BOUGHT, TICKETS_LIMIT, TICKETS_LINE, TICKETS_NO_COINS
from bot.utils.formatting import format_number
from bot.handlers.school import render_shop_block

router = Router(name="shop")


async def render_shop(session: AsyncSession, redis: Redis, user_id: int):
    """Экран магазина. Публичный — его же перерисовывает раздел «Обучение» (`handlers/school`)."""
    quest = await mastery_repo.get(session, user_id)
    free = quest.points_free if quest is not None else 0
    wallet = await business_repo.get_wallet(session, user_id)
    school_text, school_rows = await render_shop_block(session, redis, user_id)
    offer = await shop_svc.tickets_offer(redis, user_id)
    tickets = TICKETS_LINE.format(price=format_number(offer.price), left=offer.left, limit=offer.limit)
    items = tickets + (f"\n{FREE_POINTS.format(free=free)}" if free else "") + school_text
    text = SHOP_SCREEN.format(coins=format_number(wallet.nh_coins if wallet else 0), items=items)
    return text, shop_menu(has_free_points=free > 0, extra_rows=school_rows, tickets_left=offer.left)


@router.callback_query(F.data == CB_MENU_SHOP)
async def cb_shop_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = await render_shop(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_SHOP_TICKETS_PREFIX))
async def cb_shop_tickets(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    try:
        amount = int(callback.data.removeprefix(CB_SHOP_TICKETS_PREFIX))
        cost = await shop_svc.buy_tickets(session, redis, callback.from_user.id, amount)
    except ValueError:
        await callback.answer()
        return
    except shop_svc.ShopBusyError:
        await callback.answer(SHOP_BUSY)
        return
    except shop_svc.TicketsDailyLimitError as exc:
        await callback.answer(TICKETS_LIMIT.format(left=exc.left), show_alert=True)
        return
    except shop_svc.TicketsNotEnoughCoinsError as exc:
        await callback.answer(TICKETS_NO_COINS.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer(TICKETS_BOUGHT.format(n=amount, cost=format_number(cost)), show_alert=True)
    text, markup = await render_shop(session, redis, callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:  # то же сообщение или старое — не страшно
        pass
