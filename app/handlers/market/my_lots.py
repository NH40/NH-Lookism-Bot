import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import html

from app.models.user import User
from app.models.market import MarketListing
from app.services.market_service import market_service
from app.utils.formatters import fmt_num

router = Router()


@router.callback_query(F.data == "market_my_listings")
async def cb_market_my_listings(cb: CallbackQuery, session: AsyncSession, user: User):
    listings = await market_service.get_my_listings(session, user.id)
    builder = InlineKeyboardBuilder()
    if not listings:
        builder.row(InlineKeyboardButton(text="➕ Создать товар", callback_data="market_create"))
    else:
        for listing in listings:
            label = market_service.get_item_label(listing.item_type)
            meta = json.loads(listing.item_meta) if listing.item_meta else {}
            rank_str = f" [{meta.get('rank')}]" if meta.get("rank") else ""
            char_str = f" {meta.get('char_id')}" if meta.get("char_id") else ""
            builder.row(InlineKeyboardButton(
                text=f"{label}{rank_str}{char_str} x{listing.item_amount} — {fmt_num(listing.price)} NHCoin",
                callback_data=f"market_my_item:{listing.id}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_seller"))
    try:
        await cb.message.edit_text(
            f"📦 <b>Мои товары</b>\n\n"
            + (f"У вас нет активных товаров." if not listings else f"Активных: {len(listings)}/5"),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_my_item:"))
async def cb_market_my_item(cb: CallbackQuery, session: AsyncSession, user: User):
    listing_id = int(cb.data.split(":")[1])
    result = await session.execute(
        select(MarketListing).where(
            MarketListing.id == listing_id,
            MarketListing.seller_id == user.id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        await cb.answer("Товар не найден", show_alert=True)
        return

    label = market_service.get_item_label(listing.item_type)
    meta = json.loads(listing.item_meta) if listing.item_meta else {}

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Снять с продажи",
        callback_data=f"market_cancel:{listing_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_my_listings"))

    meta_str = ""
    if meta.get("rank"):
        meta_str += f"\nРанг: <b>{meta['rank']}</b>"
    if meta.get("char_id"):
        meta_str += f"\nПерсонаж: <b>{html.escape(str(meta['char_id']))}</b>"
    if meta.get("power"):
        meta_str += f"\nМощь: <b>{fmt_num(meta['power'])}</b>"

    try:
        await cb.message.edit_text(
            f"📦 <b>Мой товар #{listing.id}</b>\n\n"
            f"Тип: {label}\n"
            f"Количество: <b>{listing.item_amount}</b>"
            f"{meta_str}\n\n"
            f"Цена: <b>{fmt_num(listing.price)} NHCoin</b>\n"
            f"Статус: {'🟢 Активен' if not listing.is_sold else '✅ Продан'}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_cancel:"))
async def cb_market_cancel(cb: CallbackQuery, session: AsyncSession, user: User):
    listing_id = int(cb.data.split(":")[1])
    result = await market_service.cancel_listing(session, user, listing_id)
    if result["ok"]:
        await cb.answer("✅ Товар снят с продажи, ресурс возвращён", show_alert=True)
        await cb_market_my_listings(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)
