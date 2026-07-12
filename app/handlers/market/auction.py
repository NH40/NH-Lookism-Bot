"""Аукционы на бирже: просмотр, ставки, свои лоты."""
from datetime import datetime, timezone
import json
import html

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.market import MarketAuction
from app.services.market_auction_service import market_auction_service
from app.services.market_service import market_service
from app.services.bank.casino.common import CASINO_RESOURCES, get_balance
from app.constants.market import ITEM_TYPES
from app.utils.formatters import fmt_num, fmt_ttl
from app.utils.keyboards.common import back_kb

router = Router()

PAGE_SIZE = 8


class AuctionBidFSM(StatesGroup):
    waiting_amount = State()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ttl(auction: MarketAuction) -> str:
    now = _now() if auction.ends_at.tzinfo else datetime.utcnow()
    remaining = int((auction.ends_at - now).total_seconds())
    return fmt_ttl(remaining)


# ── Меню аукционов ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_auction_menu")
async def cb_market_auction_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Активные аукционы", callback_data="market_auction_browse"))
    builder.row(InlineKeyboardButton(text="🔨 Создать аукцион", callback_data="market_create"))
    builder.row(InlineKeyboardButton(text="📦 Мои аукционы", callback_data="market_my_auctions"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_menu"))
    try:
        await cb.message.edit_text(
            "🔨 <b>Аукционы</b>\n\n"
            "Минимальная ставка + время — выигрывает тот, кто предложит больше.\n"
            "Комиссия системы: 10% с выигрышной ставки.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Просмотр по категориям ────────────────────────────────────────────────────

@router.callback_query(F.data == "market_auction_browse")
async def cb_market_auction_browse(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    for item_type, label in ITEM_TYPES.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"market_auction_cat:{item_type}:0"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_auction_menu"))
    try:
        await cb.message.edit_text(
            "📋 <b>Активные аукционы</b>\n\nВыбери категорию:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("market_auction_cat:"))
async def cb_market_auction_cat(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    item_type = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    auctions = await market_auction_service.get_active_auctions(
        session, item_type=item_type, exclude_seller=user.id,
        limit=PAGE_SIZE, offset=page * PAGE_SIZE,
    )
    label = ITEM_TYPES.get(item_type, item_type)
    builder = InlineKeyboardBuilder()

    if not auctions:
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_auction_browse"))
        try:
            await cb.message.edit_text(
                f"🔨 <b>{label}</b>\n\nАукционов нет.",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    for auction in auctions:
        bid_str = f"{fmt_num(auction.current_bid)}" if auction.current_bid else f"от {fmt_num(auction.min_bid)}"
        res_label = CASINO_RESOURCES.get(auction.resource, auction.resource)
        builder.row(InlineKeyboardButton(
            text=f"x{auction.item_amount} — {bid_str} {res_label} | ⏳ {_ttl(auction)}",
            callback_data=f"market_auction_item:{auction.id}",
        ))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"market_auction_cat:{item_type}:{page-1}"))
    if len(auctions) == PAGE_SIZE:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"market_auction_cat:{item_type}:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_auction_browse"))

    try:
        await cb.message.edit_text(
            f"🔨 <b>{label}</b>\n\nСтр. {page+1}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


def _meta_str(item_type: str, meta: dict) -> str:
    s = ""
    if meta.get("rank"):
        s += f"\nРанг: <b>{meta['rank']}</b>"
    if meta.get("char_id"):
        s += f"\nПерсонаж: <b>{html.escape(str(meta['char_id']))}</b>"
    if item_type == "character" and meta.get("level") is not None:
        from app.constants.cards import LEVEL_LABELS
        lvl_lbl = LEVEL_LABELS.get(meta["level"], f"Ур.{meta['level']}")
        s += f"\nУровень: <b>{lvl_lbl}</b>"
    if meta.get("power"):
        s += f"\nМощь: <b>{fmt_num(meta['power'])}</b>"
    return s


@router.callback_query(F.data.startswith("market_auction_item:"))
async def cb_market_auction_item(cb: CallbackQuery, session: AsyncSession, user: User):
    auction_id = int(cb.data.split(":")[1])
    await _render_auction_item(cb, session, user, auction_id)


async def _render_auction_item(cb: CallbackQuery, session: AsyncSession, user: User, auction_id: int):
    auction = await session.get(MarketAuction, auction_id)
    if not auction or auction.is_finished or auction.is_cancelled:
        await cb.answer("Аукцион недоступен", show_alert=True)
        return

    from app.repositories.user_repo import user_repo
    seller = await user_repo.get_by_id(session, auction.seller_id)
    seller_name = html.escape(seller.full_name) if seller else "Неизвестно"

    label = market_service.get_item_label(auction.item_type)
    meta = json.loads(auction.item_meta) if auction.item_meta else {}
    res_label = CASINO_RESOURCES.get(auction.resource, auction.resource)
    min_next = market_auction_service.min_next_bid(auction)

    builder = InlineKeyboardBuilder()
    if auction.seller_id != user.id:
        builder.row(InlineKeyboardButton(
            text=f"💰 Сделать ставку (мин. {fmt_num(min_next)})",
            callback_data=f"market_auction_bid_menu:{auction_id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"market_auction_cat:{auction.item_type}:0"))

    bid_line = (
        f"Текущая ставка: <b>{fmt_num(auction.current_bid)} {res_label}</b>"
        if auction.current_bid else f"Ставок ещё нет (мин. {fmt_num(auction.min_bid)} {res_label})"
    )

    try:
        await cb.message.edit_text(
            f"🔨 <b>Аукцион #{auction.id}</b>\n\n"
            f"Тип: {label}\n"
            f"Количество: <b>{auction.item_amount}</b>"
            f"{_meta_str(auction.item_type, meta)}\n\n"
            f"{bid_line}\n"
            f"⏳ Осталось: {_ttl(auction)}\n"
            f"👤 Продавец: {seller_name}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Ставка ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("market_auction_bid_menu:"))
async def cb_market_auction_bid_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    auction_id = int(cb.data.split(":")[1])
    auction = await session.get(MarketAuction, auction_id)
    if not auction or auction.is_finished or auction.is_cancelled:
        await cb.answer("Аукцион недоступен", show_alert=True)
        return

    min_next = market_auction_service.min_next_bid(auction)
    res_label = CASINO_RESOURCES.get(auction.resource, auction.resource)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"Мин. ставка ({fmt_num(min_next)})",
        callback_data=f"market_auction_bid:{auction_id}:{min_next}",
    ))
    builder.row(InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"market_auction_bid_custom:{auction_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"market_auction_item:{auction_id}"))
    try:
        await cb.message.edit_text(
            f"💰 Ставка в {res_label} (мин. {fmt_num(min_next)}):",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


async def _place_bid_and_render(cb: CallbackQuery, session: AsyncSession, user: User, auction_id: int, amount: int):
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.market_auction_bid_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подожди...", show_alert=False)
        return

    result = await market_auction_service.place_bid(session, user, auction_id, amount)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    from app.utils.region_activity import record
    await record(session, user.id, "market")

    res_label = CASINO_RESOURCES.get(result["resource"], result["resource"])
    await cb.answer(f"✅ Ставка принята: {fmt_num(result['current_bid'])} {res_label}", show_alert=True)
    await _render_auction_item(cb, session, user, auction_id)


@router.callback_query(F.data.startswith("market_auction_bid:"))
async def cb_market_auction_bid(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    auction_id = int(parts[1])
    amount = int(parts[2])
    await _place_bid_and_render(cb, session, user, auction_id, amount)


@router.callback_query(F.data.startswith("market_auction_bid_custom:"))
async def cb_market_auction_bid_custom(cb: CallbackQuery, state: FSMContext):
    auction_id = int(cb.data.split(":")[1])
    await state.set_state(AuctionBidFSM.waiting_amount)
    await state.update_data(auction_id=auction_id)
    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="◀️ Отмена", callback_data=f"market_auction_item:{auction_id}"))
    try:
        await cb.message.edit_text(
            "✏️ Введи сумму ставки:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(AuctionBidFSM.waiting_amount)
async def msg_market_auction_bid_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    auction_id = data.get("auction_id")
    await state.clear()
    if not auction_id:
        return

    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введи корректную сумму", reply_markup=back_kb("market_auction_menu"))
        return
    amount = int(text)

    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.market_auction_bid_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await message.answer("⏳ Подожди...", reply_markup=back_kb("market_auction_menu"))
        return

    result = await market_auction_service.place_bid(session, user, auction_id, amount)
    if not result["ok"]:
        await message.answer(f"❌ {result['reason']}", reply_markup=back_kb("market_auction_menu"), parse_mode="HTML")
        return

    from app.utils.region_activity import record
    await record(session, user.id, "market")

    res_label = CASINO_RESOURCES.get(result["resource"], result["resource"])
    await message.answer(
        f"✅ Ставка принята: {fmt_num(result['current_bid'])} {res_label}",
        reply_markup=back_kb("market_auction_menu"),
        parse_mode="HTML",
    )


# ── Мои аукционы ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "market_my_auctions")
async def cb_market_my_auctions(cb: CallbackQuery, session: AsyncSession, user: User):
    auctions = await market_auction_service.get_my_auctions(session, user.id)
    builder = InlineKeyboardBuilder()
    if not auctions:
        builder.row(InlineKeyboardButton(text="🔨 Создать аукцион", callback_data="market_create"))
    else:
        for auction in auctions:
            label = market_service.get_item_label(auction.item_type)
            res_label = CASINO_RESOURCES.get(auction.resource, auction.resource)
            bid_str = fmt_num(auction.current_bid) if auction.current_bid else f"от {fmt_num(auction.min_bid)}"
            builder.row(InlineKeyboardButton(
                text=f"{label} x{auction.item_amount} — {bid_str} {res_label} | ⏳ {_ttl(auction)}",
                callback_data=f"market_my_auction:{auction.id}",
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_auction_menu"))
    try:
        await cb.message.edit_text(
            "📦 <b>Мои аукционы</b>\n\n"
            + (f"Активных: {len(auctions)}" if auctions else "У вас нет активных аукционов."),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("market_my_auction:"))
async def cb_market_my_auction(cb: CallbackQuery, session: AsyncSession, user: User):
    auction_id = int(cb.data.split(":")[1])
    auction = await session.get(MarketAuction, auction_id)
    if not auction or auction.seller_id != user.id:
        await cb.answer("Аукцион не найден", show_alert=True)
        return

    label = market_service.get_item_label(auction.item_type)
    meta = json.loads(auction.item_meta) if auction.item_meta else {}
    res_label = CASINO_RESOURCES.get(auction.resource, auction.resource)

    builder = InlineKeyboardBuilder()
    if auction.current_bid == 0 and not auction.is_finished and not auction.is_cancelled:
        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=f"market_auction_cancel:{auction_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="market_my_auctions"))

    bid_line = (
        f"Текущая ставка: <b>{fmt_num(auction.current_bid)} {res_label}</b>"
        if auction.current_bid else f"Ставок ещё нет (мин. {fmt_num(auction.min_bid)} {res_label})"
    )

    try:
        await cb.message.edit_text(
            f"📦 <b>Мой аукцион #{auction.id}</b>\n\n"
            f"Тип: {label}\n"
            f"Количество: <b>{auction.item_amount}</b>"
            f"{_meta_str(auction.item_type, meta)}\n\n"
            f"{bid_line}\n"
            f"⏳ Осталось: {_ttl(auction)}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("market_auction_cancel:"))
async def cb_market_auction_cancel(cb: CallbackQuery, session: AsyncSession, user: User):
    auction_id = int(cb.data.split(":")[1])
    result = await market_auction_service.cancel_auction(session, user, auction_id)
    if result["ok"]:
        await cb.answer("✅ Аукцион отменён, товар возвращён", show_alert=True)
        await cb_market_my_auctions(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)
