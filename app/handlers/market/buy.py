import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import html

from app.models.user import User
from app.models.market import MarketListing
from app.services.market_service import market_service
from app.services.quest_service import quest_service
from app.constants.market import ITEM_TYPES
from app.utils.formatters import fmt_num

router = Router()

PAGE_SIZE = 8


# ── Покупатель — главное меню ─────────────────────────────────────────────────

@router.callback_query(F.data == "market_buyer")
async def cb_market_buyer(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    for item_type, label in ITEM_TYPES.items():
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"market_browse:{item_type}:0"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_menu"))
    try:
        await cb.message.edit_text(
            f"🛒 <b>Покупатель</b>\n\n"
            f"💰 Ваши NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n\n"
            f"Выбери категорию:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_browse:"))
async def cb_market_browse(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    item_type = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    listings = await market_service.get_active_listings(
        session, item_type=item_type,
        exclude_seller=user.id,
        limit=PAGE_SIZE, offset=page * PAGE_SIZE
    )
    total = await session.scalar(
        select(func.count(MarketListing.id)).where(
            MarketListing.item_type == item_type,
            MarketListing.is_sold == False,
            MarketListing.is_cancelled == False,
            MarketListing.seller_id != user.id,
        )
    ) or 0

    label = market_service.get_item_label(item_type)
    builder = InlineKeyboardBuilder()

    if not listings:
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_buyer"))
        try:
            await cb.message.edit_text(
                f"🛒 <b>{label}</b>\n\nТоваров нет.",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    for listing in listings:
        from app.repositories.user_repo import user_repo
        seller = await user_repo.get_by_id(session, listing.seller_id)
        seller_name = html.escape(seller.full_name) if seller else "Неизвестно"
        meta = json.loads(listing.item_meta) if listing.item_meta else {}
        rank_str = f"[{meta.get('rank')}] " if meta.get("rank") else ""
        char_str = f"{meta.get('char_id')} " if meta.get("char_id") else ""
        level_str = ""
        if meta.get("level") is not None and listing.item_type == "character":
            from app.constants.cards import LEVEL_LABELS
            lvl = meta["level"]
            level_str = f"[{LEVEL_LABELS.get(lvl, 'Ур.' + str(lvl))}] "
        builder.row(InlineKeyboardButton(
            text=f"{rank_str}{level_str}{char_str}x{listing.item_amount} — {fmt_num(listing.price)} | {seller_name}",
            callback_data=f"market_item:{listing.id}"
        ))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️", callback_data=f"market_browse:{item_type}:{page-1}"
        ))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(
            text="▶️", callback_data=f"market_browse:{item_type}:{page+1}"
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_buyer"))

    try:
        await cb.message.edit_text(
            f"🛒 <b>{label}</b>\n\n"
            f"Найдено: {total} товаров | Стр. {page+1}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_item:"))
async def cb_market_item(cb: CallbackQuery, session: AsyncSession, user: User):
    listing_id = int(cb.data.split(":")[1])
    result = await session.execute(
        select(MarketListing).where(
            MarketListing.id == listing_id,
            MarketListing.is_sold == False,
            MarketListing.is_cancelled == False,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        await cb.answer("Товар уже недоступен", show_alert=True)
        return

    from app.repositories.user_repo import user_repo
    seller = await user_repo.get_by_id(session, listing.seller_id)
    seller_name = html.escape(seller.full_name) if seller else "Неизвестно"
    seller_username = f"@{html.escape(seller.username)}" if seller and seller.username else "—"

    label = market_service.get_item_label(listing.item_type)
    meta = json.loads(listing.item_meta) if listing.item_meta else {}

    meta_str = ""
    if meta.get("rank"):
        meta_str += f"\nРанг: <b>{meta['rank']}</b>"
    if meta.get("char_id"):
        meta_str += f"\nПерсонаж: <b>{html.escape(str(meta['char_id']))}</b>"
    if listing.item_type == "character" and meta.get("level") is not None:
        from app.constants.cards import LEVEL_LABELS
        lvl_lbl = LEVEL_LABELS.get(meta['level'], f"Ур.{meta['level']}")
        meta_str += f"\nУровень: <b>{lvl_lbl}</b>"
    if meta.get("power"):
        meta_str += f"\nМощь: <b>{fmt_num(meta['power'])}</b>"

    can_afford = "✅" if user.nh_coins >= listing.price else "❌"

    builder = InlineKeyboardBuilder()
    if user.nh_coins >= listing.price:
        builder.row(InlineKeyboardButton(
            text=f"💰 Купить за {fmt_num(listing.price)} NHCoin",
            callback_data=f"market_buy:{listing_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"market_browse:{listing.item_type}:0"
    ))

    try:
        await cb.message.edit_text(
            f"📦 <b>Товар #{listing.id}</b>\n\n"
            f"Тип: {label}\n"
            f"Количество: <b>{listing.item_amount}</b>"
            f"{meta_str}\n\n"
            f"💰 Цена: <b>{fmt_num(listing.price)} NHCoin</b>\n"
            f"👤 Продавец: {seller_name} ({seller_username})\n\n"
            f"{can_afford} У вас: {fmt_num(user.nh_coins)} NHCoin",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_buy:"))
async def cb_market_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    listing_id = int(cb.data.split(":")[1])
    result = await market_service.buy_listing(session, user, listing_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await quest_service.add_progress(session, user, "market_buy")
    from app.utils.region_activity import record
    await record(session, user.id, "market")

    label = market_service.get_item_label(result["item_type"])
    await cb.answer(
        f"✅ Куплено!\n{label} x{result['amount']}\n"
        f"Заплачено: {fmt_num(result['price'])} NHCoin",
        show_alert=True
    )
    await cb_market_buyer(cb, session, user)
