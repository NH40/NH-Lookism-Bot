from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.auction_service import auction_service
from app.utils.keyboards import back_kb
from app.utils.formatters import fmt_num, fmt_power
from datetime import datetime, timezone

router = Router()


class AuctionFSM(StatesGroup):
    waiting_bid = State()


@router.callback_query(F.data == "auction")
async def cb_auction(cb: CallbackQuery, session: AsyncSession, user: User):
    auction = await auction_service.get_active_auction(session)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()

    if not auction:
        await cb.message.edit_text(
            "🏛 <b>Аукцион</b>\n\nАукцион сейчас не проводится.\nЗаходите позже!",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
        return

    now = datetime.now(timezone.utc)
    remaining = max(0, int((auction.ends_at - now).total_seconds()))
    m, s = divmod(remaining, 60)
    time_str = f"{m}м {s}с"

    # Получаем лот
    from sqlalchemy import select
    from app.models.auction import AuctionLot, AuctionBid
    lot_r = await session.execute(
        select(AuctionLot).where(AuctionLot.auction_id == auction.id)
    )
    lot = lot_r.scalar_one_or_none()

    # Текущий лидер
    leader_str = "Нет ставок"
    if auction.winner_id:
        from app.repositories.user_repo import user_repo
        leader = await user_repo.get_by_id(session, auction.winner_id)
        if leader:
            leader_str = f"{leader.full_name} — {fmt_num(auction.final_bid)}"

    import json
    reward_str = ""
    if lot:
        try:
            data = json.loads(lot.reward_data)
            if lot.reward_type == "coins":
                reward_str = f"💰 {fmt_num(data.get('coins', 0))} NHCoin"
            elif lot.reward_type == "potion":
                reward_str = f"🧪 {data.get('name', 'Зелье')}"
            elif lot.reward_type == "character":
                from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP
                rank = data.get("rank", "")
                emoji = RANK_EMOJI.get(rank, "❓")
                cfg = RANK_CONFIG_MAP.get(rank)
                rank_label = cfg.label if cfg else rank
                reward_str = (
                    f"{emoji} {data.get('character')} "
                    f"[{rank_label}] — {fmt_power(data.get('power', 0))}"
                )
        except Exception:
            reward_str = "Неизвестный лот"

    min_bid = max(
        lot.min_bid if lot else 100,
        auction.final_bid + 1
    )

    builder.row(InlineKeyboardButton(
        text=f"💸 Сделать ставку (от {fmt_num(min_bid)})",
        callback_data="place_bid"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    await cb.message.edit_text(
        f"🏛 <b>Аукцион — Тир {auction.tier}</b>\n\n"
        f"🎁 Лот: {reward_str}\n"
        f"⏱ До конца: {time_str}\n"
        f"👑 Лидер: {leader_str}\n"
        f"💰 Ваш баланс: {fmt_num(user.nh_coins)}\n"
        f"📊 Побед на аукционе: {user.auction_wins}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "place_bid")
async def cb_place_bid(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    await state.set_state(AuctionFSM.waiting_bid)
    await cb.message.edit_text(
        f"💸 <b>Ставка на аукционе</b>\n\n"
        f"💰 Ваш баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
        f"Введите сумму ставки:",
        reply_markup=back_kb("auction"),
        parse_mode="HTML",
    )


@router.message(AuctionFSM.waiting_bid)
async def msg_place_bid(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    try:
        amount = int(message.text.strip().replace(",", "").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную сумму")
        return

    await state.clear()
    result = await auction_service.place_bid(session, user, amount)
    if result["ok"]:
        await message.answer(
            f"✅ Ставка {fmt_num(result['bid'])} NHCoin принята!",
            reply_markup=back_kb("auction"),
        )
    else:
        await message.answer(
            f"❌ {result['reason']}",
            reply_markup=back_kb("auction"),
        )