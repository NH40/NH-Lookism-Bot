import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
    try:
        await cb.message.edit_text(
            f"🏪 <b>Биржа</b>\n\n"
            f"💰 NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n\n"
            f"Выбери роль:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


# ── ПРОДАВЕЦ ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_seller")
async def cb_market_seller(cb: CallbackQuery, session: AsyncSession, user: User):
    listings = await market_service.get_my_listings(session, user.id)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать товар", callback_data="market_create"))
    builder.row(InlineKeyboardButton(text="📦 Мои товары", callback_data="market_my_listings"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_menu"))
    try:
        await cb.message.edit_text(
            f"💰 <b>Продавец</b>\n\n"
            f"Активных товаров: <b>{len(listings)}/5</b>\n\n"
            f"Выбери действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


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


# ── Отмена создания товара ────────────────────────────────────────────────────

@router.callback_query(F.data == "market_create_cancel")
async def cb_market_create_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    for item_type, label in ITEM_TYPES.items():
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"market_create_type:{item_type}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_seller"))
    try:
        await cb.message.edit_text(
            f"➕ <b>Создать товар</b>\n\nВыбери тип товара:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


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
    try:
        await cb.message.edit_text(
            f"➕ <b>Создать товар</b>\n\nВыбери тип товара:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_create_type:"))
async def cb_market_create_type(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    item_type = cb.data.split(":")[1]

    # Статисты — выбор ранга
    if item_type == "squad_member":
        builder = InlineKeyboardBuilder()
        for rank in ["S", "A", "B", "C"]:
            from app.models.squad_member import SquadMember
            cnt = await session.scalar(
                select(func.count(SquadMember.id)).where(
                    SquadMember.user_id == user.id,
                    SquadMember.rank == rank,
                )
            ) or 0
            builder.row(InlineKeyboardButton(
                text=f"Ранг {rank} (есть: {cnt})",
                callback_data=f"market_create_rank:{rank}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_create"))
        await state.update_data(item_type=item_type)
        try:
            await cb.message.edit_text(
                "👥 Выбери ранг статистов:",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    # Персонажи — выбор ранга
    if item_type == "character":
        from app.models.character import UserCharacter
        from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP

        rank_order = ["absolute", "peak", "legend", "new_legend", "gen_zero",
                      "strong_king", "king", "boss", "member"]

        builder = InlineKeyboardBuilder()
        has_any = False
        for rank in rank_order:
            cnt = await session.scalar(
                select(func.count(UserCharacter.id)).where(
                    UserCharacter.user_id == user.id,
                    UserCharacter.rank == rank,
                )
            ) or 0
            if cnt > 0:
                has_any = True
                emoji = RANK_EMOJI.get(rank, "⭐")
                label = RANK_CONFIG_MAP[rank].label if rank in RANK_CONFIG_MAP else rank
                builder.row(InlineKeyboardButton(
                    text=f"{emoji} {label} (есть: {cnt})",
                    callback_data=f"market_char_rank:{rank}"
                ))

        if not has_any:
            await cb.answer("У вас нет персонажей", show_alert=True)
            return

        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_create"))
        await state.update_data(item_type=item_type)
        try:
            await cb.message.edit_text(
                "⭐ Выбери ранг персонажа:",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    # Остальные типы — показываем баланс
    balance_str = ""
    if item_type == "tickets":
        balance_str = f"У вас: <b>{user.tickets}</b> тикетов"
    elif item_type == "path_points":
        balance_str = f"У вас: <b>{user.skill_path_points}</b> очков пути"
    elif item_type == "mastery_points":
        balance_str = f"У вас: <b>{user.mastery_points}</b> очков мастерства"
    elif item_type == "ui_fragments":
        balance_str = f"У вас: <b>{user.ui_fragments}</b> фрагментов УИ"

    await state.update_data(item_type=item_type, meta={})
    await state.set_state(MarketFSM.waiting_amount)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="market_create_cancel"))
    try:
        await cb.message.edit_text(
            f"➕ <b>{ITEM_TYPES[item_type]}</b>\n\n"
            f"{balance_str}\n\n"
            f"Введи количество:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_create_rank:"))
async def cb_market_create_rank(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    rank = cb.data.split(":")[1]
    from app.models.squad_member import SquadMember
    count = await session.scalar(
        select(func.count(SquadMember.id)).where(
            SquadMember.user_id == user.id,
            SquadMember.rank == rank,
        )
    ) or 0

    if count == 0:
        await cb.answer(f"У вас нет статистов ранга {rank}", show_alert=True)
        return

    await state.update_data(item_type="squad_member", meta={"rank": rank}, max_amount=count)
    await state.set_state(MarketFSM.waiting_amount)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="market_create_cancel"))
    try:
        await cb.message.edit_text(
            f"👥 <b>Статисты ранга {rank}</b>\n\n"
            f"У вас: <b>{count}</b> штук\n\n"
            f"Введи количество для продажи (макс {count}):",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_char_rank:"))
async def cb_market_char_rank(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    rank = cb.data.split(":")[1]
    from app.models.character import UserCharacter
    from app.data.characters import RANK_EMOJI

    result = await session.execute(
        select(UserCharacter).where(
            UserCharacter.user_id == user.id,
            UserCharacter.rank == rank,
        )
    )
    chars = result.scalars().all()

    if not chars:
        await cb.answer("Нет персонажей этого ранга", show_alert=True)
        return

    # Группируем одинаковых персонажей
    char_map: dict[str, list] = {}
    for char in chars:
        if char.character_id not in char_map:
            char_map[char.character_id] = []
        char_map[char.character_id].append(char)

    emoji = RANK_EMOJI.get(rank, "⭐")
    builder = InlineKeyboardBuilder()
    for char_id, char_list in char_map.items():
        count = len(char_list)
        avg_power = int(sum(c.power for c in char_list) / count)
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {char_id} x{count} | 💪 {fmt_num(avg_power)}",
            callback_data=f"market_char_select:{char_id}:{rank}"
        ))

    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="market_create_type:character"
    ))
    await state.update_data(item_type="character")
    try:
        await cb.message.edit_text(
            f"{emoji} <b>Персонажи ранга {rank}</b>\n\nВыбери персонажа:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("market_char_select:"))
async def cb_market_char_select(
    cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
):
    parts = cb.data.split(":")
    char_id = parts[1]
    rank = parts[2]

    from app.models.character import UserCharacter
    result = await session.execute(
        select(UserCharacter).where(
            UserCharacter.user_id == user.id,
            UserCharacter.character_id == char_id,
            UserCharacter.rank == rank,
        )
    )
    chars = result.scalars().all()

    if not chars:
        await cb.answer("Персонаж не найден", show_alert=True)
        return

    count = len(chars)
    avg_power = int(sum(c.power for c in chars) / count)

    await state.update_data(
        item_type="character",
        meta={
            "char_id": char_id,
            "rank": rank,
            "power": avg_power,
        },
        max_amount=count,
    )
    await state.set_state(MarketFSM.waiting_amount)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="market_create_cancel"))
    try:
        await cb.message.edit_text(
            f"⭐ <b>{html.escape(char_id)}</b> [{rank}]\n"
            f"💪 Средняя мощь: {fmt_num(avg_power)}\n"
            f"У вас: <b>{count}</b> шт.\n\n"
            f"Введи количество для продажи (макс {count}):",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(MarketFSM.waiting_amount)
async def msg_market_amount(
    message: Message, session: AsyncSession, user: User, state: FSMContext
):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введи корректное число")
        return

    amount = int(text)
    data = await state.get_data()
    max_amount = data.get("max_amount")

    if max_amount and amount > max_amount:
        await message.answer(f"❌ У вас только {max_amount} шт. Введи меньше или равное:")
        return

    await state.update_data(amount=amount)
    await state.set_state(MarketFSM.waiting_price)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="market_create_cancel"))
    await message.answer(
        f"💰 Введи цену в NHCoin:",
        reply_markup=cancel_kb.as_markup(),
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
        builder.row(InlineKeyboardButton(
            text=f"{rank_str}{char_str}x{listing.item_amount} — {fmt_num(listing.price)} | {seller_name}",
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

    label = market_service.get_item_label(result["item_type"])
    await cb.answer(
        f"✅ Куплено!\n{label} x{result['amount']}\n"
        f"Заплачено: {fmt_num(result['price'])} NHCoin",
        show_alert=True
    )
    await cb_market_buyer(cb, session, user)


# ── Кланы (заглушка) ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "clans_menu")
async def cb_clans_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    try:
        await cb.message.edit_text(
            "🏯 <b>Кланы</b>\n\n"
            "🔧 В разработке...",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass