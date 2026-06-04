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
from app.data.shop import SHOP_ITEMS, SHOP_MAP, MG_TIERS, MG_TIER_MAP
from app.services.cards.craft import craft_service
from app.constants.cards import TICKET_CRAFT_COST

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


# ── Крафт пыли → тикеты ───────────────────────────────────────────────────────

@router.callback_query(F.data == "shop_craft")
async def cb_shop_craft(cb: CallbackQuery, session: AsyncSession, user: User):
    dust = getattr(user, "card_dust", 0)
    overflow = getattr(user, "circ_ticket_overflow", False)
    ticket_cap = user.max_tickets * 2 if overflow else user.max_tickets
    ticket_space = max(0, ticket_cap - user.tickets)
    can_craft = dust // TICKET_CRAFT_COST

    builder = InlineKeyboardBuilder()
    if can_craft > 0 and ticket_space > 0:
        to_craft = min(can_craft, ticket_space)
        builder.row(InlineKeyboardButton(
            text=f"⚗️ Скрафтить ×1 тикет ({TICKET_CRAFT_COST} 💎)",
            callback_data="craft_ticket_1",
        ))
        if to_craft > 1:
            builder.row(InlineKeyboardButton(
                text=f"⚗️ Скрафтить ×{to_craft} (макс)",
                callback_data=f"craft_ticket_max",
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop"))

    try:
        await cb.message.edit_text(
            f"⚗️ <b>Крафт тикетов</b>\n\n"
            f"💎 Пыль: {fmt_num(dust)}\n"
            f"🎟 Тикеты: {user.tickets}/{ticket_cap}" + (f" (лимит ×2 🌟)" if overflow else "") + "\n\n"
            f"1 тикет = {TICKET_CRAFT_COST} 💎 пыли\n"
            f"Можно скрафтить: {min(can_craft, ticket_space)} тик.\n\n"
            f"<i>Пыль получается:\n"
            f"• Распыление карточек из коллекции\n"
            f"• Победа в дуэлях</i>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "craft_ticket_1")
async def cb_craft_ticket_1(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.card_action_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подожди...", show_alert=False)
        return
    result = await craft_service.craft_ticket(session, user)
    await session.commit()
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return
    await cb.answer(
        f"⚗️ Тикет скрафтен!\n"
        f"💎 Пыль осталась: {result['dust_left']}\n"
        f"🎟 Тикеты: {result['tickets']}/{user.max_tickets}",
        show_alert=True,
    )
    await cb_shop_craft(cb, session, user)


@router.callback_query(F.data == "craft_ticket_max")
async def cb_craft_ticket_max(cb: CallbackQuery, session: AsyncSession, user: User):
    overflow = getattr(user, "circ_ticket_overflow", False)
    ticket_cap = user.max_tickets * 2 if overflow else user.max_tickets
    space = ticket_cap - user.tickets
    dust = getattr(user, "card_dust", 0)
    count = min(space, dust // TICKET_CRAFT_COST)
    if count <= 0:
        await cb.answer("Нельзя скрафтить", show_alert=True)
        return
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.card_action_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подожди...", show_alert=False)
        return
    result = await craft_service.craft_ticket_bulk(session, user, count)
    await session.commit()
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return
    await cb.answer(
        f"⚗️ Скрафтено {result['crafted']} тикетов!\n"
        f"💎 Пыль осталась: {result['dust_left']}\n"
        f"🎟 Тикеты: {result['tickets']}/{user.max_tickets}",
        show_alert=True,
    )
    await cb_shop_craft(cb, session, user)


# Имена разделов по типу зелья
_MG_TYPE_LABELS: dict[str, str] = {
    "power":     "⚔️ Зелья силы",
    "training":  "🏋 Зелья тренировки",
    "income":    "💰 Зелья богатства",
    "luck":      "🍀 Зелья удачи",
    "influence": "⚡ Зелья влияния",
    "raid_drop": "💠 Зелья охотника",
}


@router.callback_query(F.data == "shop_potions")
async def cb_shop_potions(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.potion_service import potion_service
    from datetime import datetime, timezone

    active_potions = await potion_service.get_active(session, user.id)
    active_map = {p.potion_type: p for p in active_potions}
    now = datetime.now(timezone.utc)

    builder = InlineKeyboardBuilder()

    for ptype, label in _MG_TYPE_LABELS.items():
        tiers = MG_TIERS[ptype]
        rng = f"+{tiers[0].effect_value}%–+{tiers[5].effect_value}%"
        active = active_map.get(ptype)
        if active:
            remaining = max(0, int((active.expires_at - now).total_seconds()))
            m = remaining // 60
            active_str = f" 🟢{m}м"
        else:
            active_str = ""
        builder.row(InlineKeyboardButton(
            text=f"{label} [{rng}]{active_str}",
            callback_data=f"shop_pot_type:{ptype}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop"))

    try:
        await cb.message.edit_text(
            f"🧪 <b>Зелья</b>\n\n"
            f"💰 Баланс: {fmt_num(user.nh_coins)}\n\n"
            f"Выберите тип зелья:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


async def _render_pot_type(
    cb: CallbackQuery, session: AsyncSession, user: User, ptype: str
) -> None:
    """Отрисовывает страницу тира зелий без изменения cb.data."""
    from app.services.potion_service import potion_service
    from datetime import datetime, timezone

    tiers = MG_TIERS.get(ptype)
    if not tiers:
        return

    label = _MG_TYPE_LABELS.get(ptype, "🧪 Зелья")
    builder = InlineKeyboardBuilder()
    lines   = [f"{label}\n", f"💰 Баланс: {fmt_num(user.nh_coins)}\n"]

    # Активное зелье данного типа
    active_potions = await potion_service.get_active(session, user.id)
    active = next((p for p in active_potions if p.potion_type == ptype), None)
    if active:
        now = datetime.now(timezone.utc)
        remaining = max(0, int((active.expires_at - now).total_seconds()))
        m, s = divmod(remaining, 60)
        lines.append(f"🟢 <b>Активно:</b> +{active.bonus_value}% ещё {m}м {s}с\n")

    for tier in tiers:
        can = "✅" if user.nh_coins >= tier.price else "❌"
        is_active = active and active.bonus_value == tier.effect_value
        active_mark = " 🟢" if is_active else ""
        lines.append(f"  {can} {tier.name} — {tier.description} | {fmt_num(tier.price)}{active_mark}")
        builder.row(InlineKeyboardButton(
            text=f"{can} {tier.name} | {fmt_num(tier.price)}{active_mark}",
            callback_data=f"buy_potion:{tier.potion_id}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="shop_potions"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("shop_pot_type:"))
async def cb_shop_pot_type(cb: CallbackQuery, session: AsyncSession, user: User):
    ptype = cb.data.split(":")[1]
    if not MG_TIERS.get(ptype):
        await cb.answer("Неизвестный тип", show_alert=True)
        return
    await _render_pot_type(cb, session, user, ptype)
    try:
        await cb.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("buy_potion:"))
async def cb_buy_potion(cb: CallbackQuery, session: AsyncSession, user: User):
    potion_id = cb.data.split(":")[1]
    cfg = MG_TIER_MAP.get(potion_id)
    if not cfg:
        await cb.answer("Зелье не найдено", show_alert=True)
        return
    if user.nh_coins < cfg.price:
        await cb.answer(
            f"Недостаточно монет (нужно {fmt_num(cfg.price)})",
            show_alert=True,
        )
        return

    # Лок: предотвращает двойное нажатие → двойное списание монет
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.potion_buy_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        await cb.answer("⏳ Подожди...", show_alert=False)
        return

    user.nh_coins -= cfg.price
    user.coins_spent += cfg.price

    from app.services.potion_service import potion_service
    await potion_service.apply_potion(
        session, user.id,
        cfg.effect_key, cfg.effect_value, cfg.duration_minutes,
    )
    await session.flush()

    await cb.answer(
        f"✅ {cfg.name} применено!\n+{cfg.effect_value}% на {cfg.duration_minutes} мин.",
        show_alert=True,
    )
    # Обновляем экран через хелпер — без изменения frozen cb.data
    await _render_pot_type(cb, session, user, cfg.effect_key)


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
    for qty in [1, 10, 100, 1_000, 10_000, 100_000]:
        total = price * qty
        can = "✅" if user.nh_coins >= total else "❌"
        builder.button(
            text=f"{can} {qty} шт = {fmt_num(total)}",
            callback_data=f"shop_buy_qty:{rank}:{qty}"
        )
    builder.adjust(2)
    # ── Кнопка своего числа ──
    builder.row(InlineKeyboardButton(
        text="✏️ Ввести своё количество",
        callback_data=f"shop_input_qty:{rank}"
    ))
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

@router.callback_query(F.data.startswith("shop_input_qty:"))
async def cb_shop_input_qty(
    cb: CallbackQuery, session: AsyncSession,
    user: User, state: FSMContext
):
    rank = cb.data.split(":")[1]
    from app.data.shop import RECRUIT_RANK_TO_ITEM
    item_id = RECRUIT_RANK_TO_ITEM.get(rank)
    item = SHOP_MAP.get(item_id)
    if not item:
        await cb.answer("Товар не найден", show_alert=True)
        return

    discount = user.recruit_discount_percent
    price = max(1, int(item.price * (1 - discount / 100)))

    await state.set_state(ShopFSM.waiting_recruit_count)
    await state.update_data(rank=rank, price_per=price)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Отмена", callback_data=f"shop_buy_rank:{rank}"
    ))

    try:
        await cb.message.edit_text(
            f"✏️ <b>Введите количество статистов [{rank}]</b>\n\n"
            f"Цена: {fmt_num(price)}/шт\n"
            f"Баланс: {fmt_num(user.nh_coins)}\n\n"
            f"Введите число от 1 до 1 000 000:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass

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
        if count < 1 or count > 1000000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 1 до 1000000")
        return

    result = await _do_buy_recruits(session, user, rank, count)
    if result["ok"]:
        await message.answer(
            f"✅ Куплено <b>{result['count']}</b> бойцов [{rank}]!\n"
            f"Потрачено: {fmt_num(result['total_cost'])} NHCoin",
            reply_markup=back_kb("shop_recruits"),
            parse_mode="HTML",
        )
    else:
        await message.answer(result["reason"], reply_markup=back_kb("shop_recruits"))

async def _do_buy_recruits(
    session: AsyncSession, user: User, rank: str, count: int
) -> dict:
    from app.services.cooldown_service import cooldown_service
    from app.services.squad_service import squad_service
    lock_key = cooldown_service.buy_recruit_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=5):
        return {"ok": False, "reason": "Подожди..."}
    return await squad_service.buy_recruit(session, user, rank, count)

