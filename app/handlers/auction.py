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


def _fmt_time(seconds: int) -> str:
    if seconds <= 0:
        return "завершается..."
    m, s = divmod(seconds, 60)
    return f"{m}м {s}с" if m else f"{s}с"


async def _render_auction(
    cb: CallbackQuery, session: AsyncSession, user: User
) -> None:
    data = await auction_service.get_display_data(session, user)

    if not data["active"]:
        wait = data.get("wait_seconds", 0)
        if wait > 0:
            m, s = divmod(wait, 60)
            wait_str = f"{m}м {s}с"
            msg = f"🏛 <b>Аукцион</b>\n\nСледующий аукцион начнётся через: {wait_str}"
        else:
            msg = "🏛 <b>Аукцион</b>\n\nСледующий аукцион скоро начнётся!"

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🔄 Обновить", callback_data="auction"
        ))
        builder.row(InlineKeyboardButton(
            text="◀️ Главное меню", callback_data="main_menu"
        ))
        try:
            await cb.message.edit_text(
                msg,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    leader_str = data["leader_name"]
    if data["is_leader"]:
        leader_str = f"👑 {leader_str} (вы лидируете!)"

    text = (
        f"{data['tier_emoji']} <b>Аукцион — {data['tier_name']}</b>\n"
        f"Раунд {data['current_round']}/{data['total_rounds']}\n\n"
        f"🎁 Лот: {data['reward_str']}\n"
        f"💰 Текущая ставка: {fmt_num(data['current_bid'])} NHCoin\n"
        f"📊 Ставок: {data['bids_count']}\n"
        f"👑 Лидер: {leader_str}\n"
        f"⏱ Осталось: {_fmt_time(data['remaining'])}\n\n"
        f"💼 Твой баланс: {fmt_num(user.nh_coins)} NHCoin\n"
        f"📌 Мин. ставка: {fmt_num(data['min_next_bid'])} NHCoin"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"📈 +5% ({fmt_num(data['bid_5'])})",
            callback_data=f"auction_bid:{data['bid_5']}"
        ),
        InlineKeyboardButton(
            text=f"📈 +10% ({fmt_num(data['bid_10'])})",
            callback_data=f"auction_bid:{data['bid_10']}"
        ),
        InlineKeyboardButton(
            text=f"📈 +50% ({fmt_num(data['bid_50'])})",
            callback_data=f"auction_bid:{data['bid_50']}"
        ),
    )
    builder.row(InlineKeyboardButton(
        text="✏️ Своя ставка", callback_data="auction_custom"
    ))
    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data="auction"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    try:
        await cb.message.edit_text(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "auction")
async def cb_auction(cb: CallbackQuery, session: AsyncSession, user: User):
    await _render_auction(cb, session, user)
    await cb.answer()


@router.callback_query(F.data.startswith("auction_bid:"))
async def cb_auction_bid(cb: CallbackQuery, session: AsyncSession, user: User):
    amount = int(cb.data.split(":")[1])
    result = await auction_service.place_bid(session, user, amount)
    if result["ok"]:
        await cb.answer(f"✅ Ставка {fmt_num(amount)} принята!")
    else:
        await cb.answer(result["reason"], show_alert=True)
    await _render_auction(cb, session, user)


@router.callback_query(F.data == "auction_custom")
async def cb_auction_custom(
    cb: CallbackQuery, session: AsyncSession,
    user: User, state: FSMContext
):
    data = await auction_service.get_display_data(session, user)
    if not data["active"]:
        await cb.answer("Аукцион не активен", show_alert=True)
        return

    await state.set_state(AuctionFSM.waiting_bid)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="auction"
    ))
    try:
        await cb.message.edit_text(
            f"✏️ <b>Введите сумму ставки</b>\n\n"
            f"Мин. ставка: {fmt_num(data['min_next_bid'])} NHCoin\n"
            f"Твой баланс: {fmt_num(user.nh_coins)} NHCoin",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(AuctionFSM.waiting_bid)
async def msg_auction_bid(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    await state.clear()
    try:
        amount = int(
            message.text.strip().replace(",", "").replace(" ", "")
        )
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