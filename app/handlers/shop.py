from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.keyboards import shop_kb, back_kb
from app.utils.formatters import fmt_num
from app.data.shop import POTIONS, SHOP_ITEMS, POTION_MAP, SHOP_MAP

router = Router()


class ShopFSM(StatesGroup):
    waiting_points_count = State()


@router.callback_query(F.data == "shop")
async def cb_shop(cb: CallbackQuery, session: AsyncSession, user: User):
    await cb.message.edit_text(
        f"🛒 <b>Магазин</b>\n\n"
        f"💰 Баланс: {fmt_num(user.nh_coins)} NHCoin\n"
        f"💎 Очки пути: {user.skill_path_points}\n\n"
        f"Выберите раздел:",
        reply_markup=shop_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "shop_potions")
async def cb_shop_potions(cb: CallbackQuery, session: AsyncSession, user: User):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for p in POTIONS:
        can = "✅" if user.nh_coins >= p.price else "❌"
        builder.button(
            text=f"{can} {p.name} | {fmt_num(p.price)}",
            callback_data=f"buy_potion:{p.potion_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="shop"))

    lines = ["🧪 <b>Зелья</b>\n", f"💰 Баланс: {fmt_num(user.nh_coins)}\n"]
    for p in POTIONS:
        lines.append(
            f"{p.name}\n"
            f"  └ {p.description} | {fmt_num(p.price)} монет"
        )
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
        f"✅ {cfg.name} применено!\n"
        f"+{cfg.effect_value}% на {cfg.duration_minutes} мин"
    )
    await cb_shop_potions(cb, session, user)


@router.callback_query(F.data == "shop_points")
async def cb_shop_points(cb: CallbackQuery, session: AsyncSession, user: User):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    point_items = [i for i in SHOP_ITEMS if i.category == "path_points"]
    for item in point_items:
        can = "✅" if user.nh_coins >= item.price else "❌"
        builder.button(
            text=f"{can} {item.name} | {fmt_num(item.price)}",
            callback_data=f"buy_points:{item.item_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="shop"))

    await cb.message.edit_text(
        f"🔷 <b>Очки пути</b>\n\n"
        f"💰 Баланс: {fmt_num(user.nh_coins)} NHCoin\n"
        f"💎 Текущие очки: {user.skill_path_points}\n\n"
        f"Выберите пакет:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy_points:"))
async def cb_buy_points(cb: CallbackQuery, session: AsyncSession, user: User):
    item_id = cb.data.split(":")[1]
    item = SHOP_MAP.get(item_id)
    if not item:
        await cb.answer("Товар не найден", show_alert=True)
        return
    if user.nh_coins < item.price:
        await cb.answer(
            f"Недостаточно монет (нужно {fmt_num(item.price)})",
            show_alert=True
        )
        return

    # Определяем количество очков
    points_map = {"points_1": 1, "points_3": 3, "points_5": 5}
    points = points_map.get(item_id, 1)

    user.nh_coins -= item.price
    user.coins_spent += item.price
    user.skill_path_points += points
    await session.flush()

    await cb.answer(f"✅ Куплено {points} очков пути!")
    await cb_shop_points(cb, session, user)


@router.callback_query(F.data == "shop_recruits")
async def cb_shop_recruits(cb: CallbackQuery, session: AsyncSession, user: User):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    recruit_items = [i for i in SHOP_ITEMS if i.category == "recruit"]
    builder = InlineKeyboardBuilder()
    for item in recruit_items:
        discount = user.recruit_discount_percent
        price = max(1, int(item.price * (1 - discount / 100)))
        can = "✅" if user.nh_coins >= price else "❌"
        builder.button(
            text=f"{can} {item.name} | {fmt_num(price)}/шт",
            callback_data=f"shop_recruit_rank:{item.item_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="shop"))

    await cb.message.edit_text(
        f"👥 <b>Статисты</b>\n\n"
        f"💰 Баланс: {fmt_num(user.nh_coins)}\n"
        f"Скидка: {user.recruit_discount_percent}%\n\n"
        f"Выберите ранг и введите количество:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )