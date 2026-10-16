"""Магазин — верхнеуровневый таб (хендлеры).

Содержание магазина в raw-notes не описано; первый товар — тренер Том Ли (очки мастерства
за NHCoin), открывается после победы над Томом в цепочке «Преодоление стены» (пользователь
2026-09-30: «получает возможность в магазине открыть тренера»). Остальное (чёрный рынок и
донат — см. память о донате) — позже.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS
from bot.constant.common import CB_MENU_SHOP
from bot.constant.mastery import QUEST_TRAINER
from bot.constant.shop import CB_SHOP_BUY_MASTERY_POINT, LOCK_ACTION_SHOP
from bot.db.repositories import business as business_repo
from bot.keyboards.shop import shop_menu
from bot.services.gang import get_gang
from bot.services.mastery import NotEnoughCoinsError, PointsSoldOutError, TrainerLockedError, buy_point, get_view
from bot.texts.mastery import STAGE_NAMES
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.shop import (
    BOUGHT,
    BUSY,
    NOT_ENOUGH,
    SHOP_SCREEN,
    SOLD_OUT,
    TRAINER_AVAILABLE,
    TRAINER_LOCKED,
    TRAINER_LOCKED_ALERT,
)
from bot.utils.formatting import format_countdown, format_number
from bot.handlers.school import render_shop_block
from bot.utils.safe_edit import safe_edit_text

router = Router(name="shop")


async def render_shop(session: AsyncSession, redis: Redis, user_id: int):
    """Экран магазина. Публичный — его же перерисовывает раздел «Обучение» (`handlers/school`)."""
    view = await get_view(session, user_id)
    wallet = await business_repo.get_wallet(session, user_id)
    trainer = view.status == QUEST_TRAINER
    items = (
        TRAINER_AVAILABLE.format(
            price=format_number(view.price or 0),
            stage_name=STAGE_NAMES.get(view.stage, ""),
            bought=view.points_bought,
            free=view.points_free,
        )
        if trainer
        else TRAINER_LOCKED
    )
    school_text, school_rows = await render_shop_block(session, redis, user_id)
    items += school_text
    text = SHOP_SCREEN.format(coins=format_number(wallet.nh_coins if wallet else 0), items=items)
    buy_price = view.price if trainer and view.points_bought < 4 else None
    return text, shop_menu(
        buy_price=buy_price, has_free_points=view.points_free > 0,
        extra_rows=school_rows,
    )


@router.callback_query(F.data == CB_MENU_SHOP)
async def cb_shop_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = await render_shop(session, redis, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data == CB_SHOP_BUY_MASTERY_POINT)
async def cb_shop_buy_point(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user_id = callback.from_user.id
    key = action_lock(user_id, LOCK_ACTION_SHOP)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        await callback.answer(BUSY)
        return
    try:
        result = await buy_point(session, user_id)
    except TrainerLockedError:
        await callback.answer(TRAINER_LOCKED_ALERT, show_alert=True)
        return
    except PointsSoldOutError:
        await callback.answer(SOLD_OUT, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(
            NOT_ENOUGH.format(cost=format_number(exc.cost), balance=format_number(exc.balance)), show_alert=True
        )
        return
    finally:
        await redis.delete(key)
    # Popup — без HTML.
    await callback.answer(BOUGHT.format(price=format_number(result.price)))
    text, markup = await render_shop(session, redis, user_id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
