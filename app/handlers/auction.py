from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.auction_service import auction_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


class AuctionFSM(StatesGroup):
    waiting_bid = State()


def _format_remaining(seconds: int) -> str:
    if seconds <= 0:
        return "завершается..."
    m, s = divmod(seconds, 60)
    if m:
        return f"{m}м {s}с"
    return f"{s}с"


async def _render_auction(
    cb: CallbackQuery, session: AsyncSession, user: User
) -> None:
    data = await auction_service.get_auction_display(session, user)

    if not data["active"]:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🔄 Обновить", callback_data="auction"
        ))
        builder.row(InlineKeyboardButton(
            text="◀️ Главное меню", callback_data="main_menu"
        ))
        try:
            await cb.message.edit_text(
                "🏛 <b>Аукцион</b>\n\nАукцион сейчас не проводится.\nЗаходите позже!",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    remaining_str = _format_remaining(data["remaining"])
    leader_str = data["leader_name"]
    if data["is_leader"]:
        leader_str = f"👑 {leader_str} (вы лидируете!)"

    current_bid = data["current_bid"]
    min_next = data["min_next_bid"]

    # Быстрые ставки (+5%, +10%, +50%)
    bid_5 = max(min_next, int(current_bid * 1.05)) if current_bid > 0 else min_next
    bid_10 = max(min_next, int(current_bid * 1.10)) if current_bid > 0 else int(min_next * 1.1)
    bid_50 = max(min_next, int(current_bid * 1.50)) if current_bid > 0 else int(min_next * 1.5)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"📈 +5% ({fmt_num(bid_5)})",
            callback_data=f"auction_quick_bid:{bid_5}"
        ),
        InlineKeyboardButton(
            text=f"📈 +10% ({fmt_num(bid_10)})",
            callback_data=f"auction_quick_bid:{bid_10}"
        ),
        InlineKeyboardButton(
            text=f"📈 +50% ({fmt_num(bid_50)})",
            callback_data=f"auction_quick_bid:{bid_50}"
        ),
    )
    builder.row(InlineKeyboardButton(
        text="✏️ Своя ставка",
        callback_data="auction_custom_bid"
    ))
    builder.row(InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="auction"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню",
        callback_data="main_menu"
    ))

    text = (
        f"{data['tier_emoji']} <b>Аукцион — {data['tier_name']}</b>\n"
        f"Раунд {data['current_round']}/{data['total_rounds']}\n\n"
        f"🎁 Лот: {data['reward_str']}\n"
        f"💰 Текущая ставка: {fmt_num(current_bid)} NHCoin\n"
        f"📊 Ставок: {data['bids_count']}\n"
        f"👑 Лидер: {leader_str}\n"
        f"⏱ Осталось: {remaining_str}\n\n"
        f"💼 Твой баланс: {fmt_num(user.nh_coins)} NHCoin\n"
        f"📌 Мин. ставка: {fmt_num(min_next)} NHCoin"
    )

    try:
        await cb.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "auction")
async def cb_auction(cb: CallbackQuery, session: AsyncSession, user: User):
    await _render_auction(cb, session, user)
    await cb.answer()


@router.callback_query(F.data.startswith("auction_quick_bid:"))
async def cb_auction_quick_bid(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    amount = int(cb.data.split(":")[1])
    result = await auction_service.place_bid(session, user, amount)
    if result["ok"]:
        await cb.answer(f"✅ Ставка {fmt_num(amount)} принята!")
    else:
        await cb.answer(result["reason"], show_alert=True)
    await _render_auction(cb, session, user)


@router.callback_query(F.data == "auction_custom_bid")
async def cb_auction_custom_bid(
    cb: CallbackQuery, session: AsyncSession,
    user: User, state: FSMContext
):
    data = await auction_service.get_auction_display(session, user)
    if not data["active"]:
        await cb.answer("Аукцион не активен", show_alert=True)
        return

    await state.set_state(AuctionFSM.waiting_bid)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="auction"))
    await cb.message.edit_text(
        f"✏️ <b>Введите сумму ставки</b>\n\n"
        f"Минимальная ставка: {fmt_num(data['min_next_bid'])} NHCoin\n"
        f"Ваш баланс: {fmt_num(user.nh_coins)} NHCoin",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.message(AuctionFSM.waiting_bid)
async def msg_auction_bid(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    await state.clear()
    try:
        amount = int(message.text.strip().replace(",", "").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную сумму")
        return

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