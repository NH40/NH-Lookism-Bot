from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.keyboards.shop import shop_kb
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num
from app.data.shop import POTIONS, SHOP_ITEMS, POTION_MAP, SHOP_MAP

router = Router()


class ShopFSM(StatesGroup):
    waiting_recruit_count = State()
    waiting_recruit_rank = State()


@router.callback_query(F.data == "shop")
async def cb_shop(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        await cb.message.edit_text(
            f"🛒 <b>Магазин</b>\n\n"
            f"💰 Баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
            f"Выберите раздел:",
            reply_markup=shop_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "shop_potions")
async def cb_shop_potions(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    for p in POTIONS:
        can = "✅" if user.nh_coins >= p.price else "❌"
        builder.button(
            text=f"{can} {p.name} | {fmt_num(p.price)}",
            callback_data=f"buy_potion:{p.potion_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop"))

    lines = ["🧪 <b>Зелья</b>\n", f"💰 Баланс: {fmt_num(user.nh_coins)}\n"]
    for p in POTIONS:
        lines.append(f"{p.name}\n  └ {p.description} | {fmt_num(p.price)} монет")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy_potion:"))
async def cb_buy_potion(cb: CallbackQuery, session: AsyncSession, user: User):
    potion_id = cb.data.split(":")[1]
    cfg = POTION_MAP.get(potion_id)
    if not cfg:
        await cb.answer("Зелье не найдено", show_alert=True)
        return
    if user.nh_coins < cfg.price:
        await cb.answer(
            f"Недостаточно монет (нужно {fmt_num(cfg.price)})",
            show_alert=True
        )
        return

    user.nh_coins -= cfg.price
    user.coins_spent += cfg.price

    from app.services.potion_service import potion_service
    await potion_service.apply_potion(
        session, user.id,
        cfg.effect_key, cfg.effect_value, cfg.duration_minutes
    )
    await session.flush()
    await cb.answer(
        f"✅ {cfg.name} применено!\n+{cfg.effect_value}% на {cfg.duration_minutes} мин"
    )
    await cb_shop_potions(cb, session, user)


@router.callback_query(F.data == "shop_recruits")
async def cb_shop_recruits(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.data.squad import PHASE_RANKS, RANKS_BY_ID
    from app.data.shop import RECRUIT_RANK_TO_ITEM

    available = PHASE_RANKS.get(user.phase, ["E", "D"])
    builder = InlineKeyboardBuilder()

    lines = [
        f"👥 <b>Покупка статистов</b>\n\n"
        f"💰 Баланс: {fmt_num(user.nh_coins)}\n"
        f"Скидка: {user.recruit_discount_percent}%\n\n"
        f"Выберите ранг:"
    ]

    for rank in available:
        item_id = RECRUIT_RANK_TO_ITEM.get(rank)
        item = SHOP_MAP.get(item_id)
        if not item:
            continue
        discount = user.recruit_discount_percent
        price = max(1, int(item.price * (1 - discount / 100)))
        rank_cfg = RANKS_BY_ID.get(rank)
        power = rank_cfg.base_power if rank_cfg else 0
        builder.button(
            text=f"[{rank}] {fmt_num(power)} силы | {fmt_num(price)}/шт",
            callback_data=f"shop_buy_rank:{rank}"
        )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop"))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("shop_buy_rank:"))
async def cb_shop_buy_rank(
    cb: CallbackQuery, session: AsyncSession,
    user: User, state: FSMContext
):
    rank = cb.data.split(":")[1]
    from app.data.shop import RECRUIT_RANK_TO_ITEM
    from app.data.squad import RANKS_BY_ID

    item_id = RECRUIT_RANK_TO_ITEM.get(rank)
    item = SHOP_MAP.get(item_id)
    if not item:
        await cb.answer("Товар не найден", show_alert=True)
        return

    discount = user.recruit_discount_percent
    price = max(1, int(item.price * (1 - discount / 100)))
    rank_cfg = RANKS_BY_ID.get(rank)
    power = rank_cfg.base_power if rank_cfg else 0

    await state.set_state(ShopFSM.waiting_recruit_count)
    await state.update_data(rank=rank, price_per=price)

    builder = InlineKeyboardBuilder()
    for qty in [1, 5, 10, 25, 50, 100]:
        total = price * qty
        can = "✅" if user.nh_coins >= total else "❌"
        builder.button(
            text=f"{can} {qty} шт = {fmt_num(total)}",
            callback_data=f"shop_buy_qty:{rank}:{qty}"
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop_recruits"))

    await cb.message.edit_text(
        f"👥 <b>Статист [{rank}]</b>\n\n"
        f"Мощь: {fmt_num(power)} за бойца\n"
        f"Цена: {fmt_num(price)}/шт\n"
        f"Баланс: {fmt_num(user.nh_coins)}\n\n"
        f"Выбери количество или введи своё число:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("shop_buy_qty:"))
async def cb_shop_buy_qty(
    cb: CallbackQuery, session: AsyncSession,
    user: User, state: FSMContext
):
    await state.clear()
    parts = cb.data.split(":")
    rank = parts[1]
    qty = int(parts[2])

    result = await _do_buy_recruits(session, user, rank, qty)
    if result["ok"]:
        await cb.answer(
            f"✅ Куплено {result['count']} бойцов [{rank}]!\n"
            f"Потрачено: {fmt_num(result['total_cost'])}"
        )
        await cb_shop_recruits(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.message(ShopFSM.waiting_recruit_count)
async def msg_recruit_count(
    message: Message, session: AsyncSession,
    user: User, state: FSMContext
):
    data = await state.get_data()
    rank = data.get("rank")
    await state.clear()

    try:
        count = int(message.text.strip())
        if count < 1 or count > 500:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 500")
        return

    result = await _do_buy_recruits(session, user, rank, count)
    if result["ok"]:
        await message.answer(
            f"✅ Куплено {result['count']} бойцов [{rank}]!\n"
            f"Потрачено: {fmt_num(result['total_cost'])} NHCoin",
            reply_markup=back_kb("shop_recruits"),
        )
    else:
        await message.answer(result["reason"], reply_markup=back_kb("shop_recruits"))


async def _do_buy_recruits(
    session: AsyncSession, user: User, rank: str, count: int
) -> dict:
    from app.services.squad_service import squad_service
    return await squad_service.buy_recruit(session, user, rank, count)