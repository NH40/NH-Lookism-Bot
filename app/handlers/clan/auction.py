import json
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import ClanAuction
from app.services.clan import clan_service
from app.utils.formatters import fmt_num
from datetime import datetime, timezone

router = Router()


class ClanAuctionFSM(StatesGroup):
    waiting_bid = State()


@router.callback_query(F.data == "clan_auction_info")
async def cb_clan_auction_info(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    active = await clan_service.get_active_auction(session, clan.id)
    if active:
        cb.data = f"clan_auction:{active.id}"
        await cb_clan_auction(cb, session, user)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Купить аукцион в магазине", callback_data="clan_shop_cat:auction"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))
    try:
        await cb.message.edit_text(
            "🏛 <b>Клановый аукцион</b>\n\n"
            "Сейчас активного аукциона нет.\n\n"
            "Запустить аукцион можно через магазин клана:\n"
            "• Обычный — 1.5M NHCoin\n"
            "  └ Приз: до 7M монет, тикеты, статисты, фрагменты пути\n"
            "• Редкий — 7.5M NHCoin\n"
            "  └ Приз: до 35M монет, персонажи, мастерство\n"
            "• Эпический — 20M NHCoin\n"
            "  └ Приз: до 150M монет, LR/MP статисты, UI-фрагменты\n\n"
            "Победитель получает приз, остальные возвращают ставки.\n"
            "Только участники клана могут делать ставки.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_auction:"))
async def cb_clan_auction(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext = None):
    auction_id = int(cb.data.split(":")[1])
    auction = await session.scalar(select(ClanAuction).where(ClanAuction.id == auction_id))
    if not auction:
        await cb.answer("Аукцион не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    try:
        ends_at = auction.ends_at
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        remaining = max(0, int((ends_at - now).total_seconds()))
    except Exception:
        remaining = 0

    try:
        reward = json.loads(auction.reward_data) if auction.reward_data else {}
    except Exception:
        reward = {}

    reward_str = reward.get("label", f"{reward.get('type', '?')} x{reward.get('amount', '?')}")

    leader = None
    if auction.leader_id:
        leader = await session.scalar(select(User).where(User.id == auction.leader_id))

    builder = InlineKeyboardBuilder()
    if remaining > 0 and not auction.is_finished:
        builder.row(InlineKeyboardButton(
            text="💰 Сделать ставку",
            callback_data=f"clan_bid:{auction_id}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"clan_auction:{auction_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    if auction.is_finished:
        status = "✅ Завершён"
    elif remaining >= 3600:
        h, m = divmod(remaining // 60, 60)
        status = f"⏳ До конца: {h}ч {m}м"
    elif remaining >= 60:
        m, s = divmod(remaining, 60)
        status = f"⏳ До конца: {m}м {s}с"
    else:
        status = f"⏳ До конца: {remaining}с"

    min_bid = auction.current_bid + max(1, int(auction.current_bid * 0.1)) if auction.current_bid > 0 else 1
    is_leader = leader and leader.id == user.id

    lines = [
        f"🏛 <b>Клановый аукцион</b>",
        f"",
        f"🎁 Приз: <b>{reward_str}</b>",
        f"💰 Текущая ставка: <b>{fmt_num(auction.current_bid)} NHCoin</b>",
        f"👤 Лидер: {html.escape(leader.full_name) if leader else 'нет'}",
    ]
    if not auction.is_finished and remaining > 0:
        if is_leader:
            lines.append(f"✅ Вы лидер аукциона!")
        else:
            lines.append(f"💡 Мин. ставка: {fmt_num(min_bid)} NHCoin")
    lines.append(f"")
    lines.append(status)

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("clan_bid:"))
async def cb_clan_bid(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    auction_id = int(cb.data.split(":")[1])
    auction = await session.scalar(select(ClanAuction).where(ClanAuction.id == auction_id))
    if not auction:
        await cb.answer("Аукцион не найден", show_alert=True)
        return

    await state.set_state(ClanAuctionFSM.waiting_bid)
    await state.update_data(auction_id=auction_id)

    min_bid = auction.current_bid + max(1, int(auction.current_bid * 0.1)) if auction.current_bid > 0 else 1

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data=f"clan_auction:{auction_id}"
    ))
    try:
        await cb.message.edit_text(
            f"💰 <b>Сделать ставку</b>\n\n"
            f"Текущая ставка: {fmt_num(auction.current_bid)} NHCoin\n"
            f"Минимальная ставка: {fmt_num(min_bid)} NHCoin\n"
            f"У вас: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"Введите сумму ставки:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(ClanAuctionFSM.waiting_bid)
async def msg_clan_bid(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    auction_id = data.get("auction_id")

    auction = await session.scalar(select(ClanAuction).where(ClanAuction.id == auction_id))
    if not auction:
        await message.answer("❌ Аукцион не найден")
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    result = await clan_service.bid_auction(session, auction, user, amount)
    if result["ok"]:
        await message.answer(
            f"✅ Ставка <b>{fmt_num(amount)} NHCoin</b> принята!\n"
            f"Вы лидер аукциона.",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ {result['reason']}")