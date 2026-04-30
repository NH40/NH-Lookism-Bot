import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.market import MarketListing
from app.services.market_service import market_service
from app.constants.market import ITEM_TYPES
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num
import html

router = Router()

PAGE_SIZE = 8


class MarketFSM(StatesGroup):
    waiting_price = State()
    waiting_amount = State()


# ── Главное меню биржи ────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_menu")
async def cb_market_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Покупатель", callback_data="market_buyer"))
    builder.row(InlineKeyboardButton(text="💰 Продавец", callback_data="market_seller"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    await cb.message.edit_text(
        f"🏪 <b>Биржа</b>\n\n"
        f"💰 NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n\n"
        f"Выбери роль:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── ПРОДАВЕЦ ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_seller")
async def cb_market_seller(cb: CallbackQuery, session: AsyncSession, user: User):
    listings = await market_service.get_my_listings(session, user.id)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать товар", callback_data="market_create"))
    builder.row(InlineKeyboardButton(text="📦 Мои товары", callback_data="market_my_listings"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_menu"))

    await cb.message.edit_text(
        f"💰 <b>Продавец</b>\n\n"
        f"Активных товаров: <b>{len(listings)}/5</b>\n\n"
        f"Выбери действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "market_my_listings")
async def cb_market_my_listings(cb: CallbackQuery, session: AsyncSession, user: User):
    listings = await market_service.get_my_listings(session, user.id)

    builder = InlineKeyboardBuilder()
    if not listings:
        builder.row(InlineKeyboardButton(text="➕ Создать товар", callback_data="market_create"))
    else:
        for listing in listings:
            label = market_service.get_item_label(listing.item_type)
            builder.row(InlineKeyboardButton(
                text=f"{label} x{listing.item_amount} — {fmt_num(listing.price)} NHCoin",
                callback_data=f"market_my_item:{listing.id}"
            ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_seller"))

    await cb.message.edit_text(
        f"📦 <b>Мои товары</b>\n\n"
        + (f"У вас нет активных товаров." if not listings else f"Активных: {len(listings)}/5"),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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
        meta_str = f"\nРанг: {meta['rank']}"
    elif meta.get("name"):
        meta_str = f"\nПерсонаж: {meta['name']}"

    await cb.message.edit_text(
        f"📦 <b>Мой товар #{listing.id}</b>\n\n"
        f"Тип: {label}\n"
        f"Количество: {listing.item_amount}"
        f"{meta_str}\n"
        f"Цена: <b>{fmt_num(listing.price)} NHCoin</b>\n"
        f"Статус: {'🟢 Активен' if not listing.is_sold else '✅ Продан'}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("market_cancel:"))
async def cb_market_cancel(cb: CallbackQuery, session: AsyncSession, user: User):
    listing_id = int(cb.data.split(":")[1])
    result = await market_service.cancel_listing(session, user, listing_id)
    if result["ok"]:
        await cb.answer("✅ Товар снят с продажи, ресурс возвращён", show_alert=True)
        await cb_market_my_listings(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


# ── Создание товара ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_create")
async def cb_market_create(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    for item_type, label in ITEM_TYPES.items():
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"market_create_type:{item_type}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_seller"))

    await cb.message.edit_text(
        f"➕ <b>Создать товар</b>\n\n"
        f"Выбери тип товара:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("market_create_type:"))
async def cb_market_create_type(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    item_type = cb.data.split(":")[1]

    # Для статистов — выбор ранга
    if item_type == "squad_member":
        builder = InlineKeyboardBuilder()
        for rank in ["S", "A", "B", "C"]:
            builder.row(InlineKeyboardButton(
                text=f"Ранг {rank}",
                callback_data=f"market_create_rank:{rank}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_create"))
        await state.update_data(item_type=item_type)
        await cb.message.edit_text(
            "👥 Выбери ранг статистов:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return

    # Для персонажей — показываем список
    if item_type == "character":
        from app.models.character import UserCharacter
        result = await session.execute(
            select(UserCharacter).where(UserCharacter.user_id == user.id).limit(20)
        )
        chars = result.scalars().all()
        if not chars:
            await cb.answer("У вас нет персонажей", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        for char in chars:
            builder.row(InlineKeyboardButton(
                text=f"⭐ {char.name} | 💪 {fmt_num(char.power)}",
                callback_data=f"market_create_char:{char.character_id}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_create"))
        await state.update_data(item_type=item_type)
        await cb.message.edit_text(
            "⭐ Выбери персонажа для продажи:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return

    await state.update_data(item_type=item_type, meta={})
    await state.set_state(MarketFSM.waiting_amount)
    await cb.message.edit_text(
        f"➕ <b>{ITEM_TYPES[item_type]}</b>\n\n"
        f"Введи количество:",
        reply_markup=back_kb("market_create"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("market_create_rank:"))
async def cb_market_create_rank(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    rank = cb.data.split(":")[1]
    from app.models.squad_member import SquadMember
    count = await session.scalar(
        select(SquadMember).where(
            SquadMember.user_id == user.id,
            SquadMember.rank == rank,
        )
    ) or 0

    await state.update_data(item_type="squad_member", meta={"rank": rank})
    await state.set_state(MarketFSM.waiting_amount)
    await cb.message.edit_text(
        f"👥 <b>Статисты ранга {rank}</b>\n\n"
        f"Введи количество для продажи:",
        reply_markup=back_kb("market_create"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("market_create_char:"))
async def cb_market_create_char(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    char_id = int(cb.data.split(":")[1])
    from app.models.character import UserCharacter
    result = await session.execute(
        select(UserCharacter).where(
            UserCharacter.user_id == user.id,
            UserCharacter.character_id == char_id,
        )
    )
    char = result.scalar_one_or_none()
    if not char:
        await cb.answer("Персонаж не найден", show_alert=True)
        return

    await state.update_data(
        item_type="character",
        meta={"char_id": char_id, "name": char.name, "power": char.power, "rarity": char.rarity},
        amount=1
    )
    await state.set_state(MarketFSM.waiting_price)
    await cb.message.edit_text(
        f"⭐ <b>{html.escape(char.name)}</b>\n"
        f"💪 Мощь: {fmt_num(char.power)}\n\n"
        f"Введи цену в NHCoin:",
        reply_markup=back_kb("market_create"),
        parse_mode="HTML",
    )


@router.message(MarketFSM.waiting_amount)
async def msg_market_amount(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введи корректное число")
        return

    amount = int(text)
    await state.update_data(amount=amount)
    await state.set_state(MarketFSM.waiting_price)
    await message.answer(
        f"💰 Введи цену в NHCoin:",
        reply_markup=back_kb("market_create"),
        parse_mode="HTML",
    )


@router.message(MarketFSM.waiting_price)
async def msg_market_price(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введи корректную цену")
        return

    price = int(text)
    data = await state.get_data()
    item_type = data.get("item_type")
    amount = data.get("amount", 1)
    meta = data.get("meta", {})

    result = await market_service.create_listing(
        session, user, item_type, amount, price, meta
    )

    await state.clear()

    if result["ok"]:
        label = market_service.get_item_label(item_type)
        await message.answer(
            f"✅ <b>Товар выставлен!</b>\n\n"
            f"{label} x{amount}\n"
            f"Цена: {fmt_num(price)} NHCoin",
            reply_markup=back_kb("market_seller"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ {result['reason']}",
            reply_markup=back_kb("market_seller"),
            parse_mode="HTML",
        )


# ── ПОКУПАТЕЛЬ ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_buyer")
async def cb_market_buyer(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    for item_type, label in ITEM_TYPES.items():
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"market_browse:{item_type}:0"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_menu"))

    await cb.message.edit_text(
        f"🛒 <b>Покупатель</b>\n\n"
        f"💰 Ваши NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n\n"
        f"Выбери категорию:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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
        __import__("sqlalchemy", fromlist=["select"]).select(
            __import__("sqlalchemy", fromlist=["func"]).func.count(MarketListing.id)
        ).where(
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
        await cb.message.edit_text(
            f"🛒 <b>{label}</b>\n\nТоваров нет.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
        return

    for listing in listings:
        from app.repositories.user_repo import user_repo
        seller = await user_repo.get_by_id(session, listing.seller_id)
        seller_name = html.escape(seller.full_name) if seller else "Неизвестно"
        builder.row(InlineKeyboardButton(
            text=f"x{listing.item_amount} — {fmt_num(listing.price)} NHCoin | {seller_name}",
            callback_data=f"market_item:{listing.id}"
        ))

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"market_browse:{item_type}:{page-1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"market_browse:{item_type}:{page+1}"))
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_buyer"))

    await cb.message.edit_text(
        f"🛒 <b>{label}</b>\n\n"
        f"Найдено: {total} товаров\n"
        f"Страница {page+1}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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
    seller_username = f"@{seller.username}" if seller and seller.username else "—"

    label = market_service.get_item_label(listing.item_type)
    meta = json.loads(listing.item_meta) if listing.item_meta else {}

    meta_str = ""
    if meta.get("rank"):
        meta_str = f"\nРанг: <b>{meta['rank']}</b>"
    elif meta.get("name"):
        meta_str = f"\nПерсонаж: <b>{html.escape(meta['name'])}</b>"
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


@router.callback_query(F.data.startswith("market_buy:"))
async def cb_market_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    listing_id = int(cb.data.split(":")[1])
    result = await market_service.buy_listing(session, user, listing_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    label = market_service.get_item_label(result["item_type"])
    await cb.answer(
        f"✅ Куплено!\n{label} x{result['amount']}\nЗаплачено: {fmt_num(result['price'])} NHCoin",
        show_alert=True
    )
    await cb_market_buyer(cb, session, user)


# ── Кланы (заглушка) ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "clans_menu")
async def cb_clans_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    await cb.message.edit_text(
        "🏯 <b>Кланы</b>\n\n"
        "🔧 В разработке...",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )