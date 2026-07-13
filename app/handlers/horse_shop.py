from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.horse_shop_service import horse_shop_service
from app.repositories.horse_shop_repo import horse_shop_repo
from app.config.game_balance import HORSE_SHOP_ITEMS, HORSE_SHOP_MAX_PER_ITEM
from app.utils.formatters import fmt_num, fmt_ttl

router = Router()


async def _build_shop_screen(session: AsyncSession, user: User):
    event = await horse_shop_service.get_current_event(session)
    if not event:
        return None

    now = datetime.now(timezone.utc)
    secs_left = max(0, int((event.expires_at - now).total_seconds()))
    purchases = await horse_shop_repo.get_user_purchases(session, event.id, user.id)

    lines = [
        "🐴 <b>Лавка коня</b>\n",
        "В честь великого торговца первого поколения была создана "
        "специальная лавка — успей купить, пока не закрылась!\n",
        f"⏳ Открыта ещё: <b>{fmt_ttl(secs_left)}</b>",
        f"💰 Твой баланс: <b>{fmt_num(user.nh_coins)}</b> NHCoin\n",
        "─" * 20,
    ]

    builder = InlineKeyboardBuilder()
    for item_id, cfg in HORSE_SHOP_ITEMS.items():
        bought = purchases.get(item_id, 0)
        lines.append(f"{cfg['name']} — {fmt_num(cfg['price'])}/шт. [{bought}/{HORSE_SHOP_MAX_PER_ITEM}]")
        builder.row(InlineKeyboardButton(
            text=f"{cfg['name']} [{bought}/{HORSE_SHOP_MAX_PER_ITEM}]",
            callback_data=f"horse_item:{item_id}",
        ))

    lines.append("\n📌 Все цены фиксированы. Торг не предусмотрен.")
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu_economy"))

    return "\n".join(lines), builder.as_markup()


@router.callback_query(F.data == "horse_shop")
async def cb_horse_shop(cb: CallbackQuery, session: AsyncSession, user: User):
    screen = await _build_shop_screen(session, user)
    if not screen:
        await cb.answer("Лавка коня сейчас закрыта", show_alert=True)
        return
    text, kb = screen
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("horse_item:"))
async def cb_horse_item(cb: CallbackQuery, session: AsyncSession, user: User):
    item_id = cb.data.split(":", 1)[1]
    cfg = HORSE_SHOP_ITEMS.get(item_id)
    if not cfg:
        await cb.answer("Товар не найден", show_alert=True)
        return

    event = await horse_shop_service.get_current_event(session)
    if not event:
        await cb.answer("Лавка коня сейчас закрыта", show_alert=True)
        return

    purchases = await horse_shop_repo.get_user_purchases(session, event.id, user.id)
    bought = purchases.get(item_id, 0)
    remaining = HORSE_SHOP_MAX_PER_ITEM - bought

    builder = InlineKeyboardBuilder()
    if remaining > 0:
        for qty in (1, 5, 10):
            if qty <= remaining:
                builder.row(InlineKeyboardButton(
                    text=f"Купить {qty} шт. ({fmt_num(cfg['price'] * qty)})",
                    callback_data=f"horse_buy:{item_id}:{qty}",
                ))
        builder.row(InlineKeyboardButton(
            text=f"Купить максимум ({remaining} шт., {fmt_num(cfg['price'] * remaining)})",
            callback_data=f"horse_buy:{item_id}:{remaining}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="horse_shop"))

    text = (
        f"{cfg['name']}\n\n"
        f"💰 Цена: <b>{fmt_num(cfg['price'])}</b> NHCoin/шт.\n"
        f"📦 Куплено: <b>{bought}/{HORSE_SHOP_MAX_PER_ITEM}</b>\n"
        f"💳 Твой баланс: <b>{fmt_num(user.nh_coins)}</b> NHCoin"
    )
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("horse_buy:"))
async def cb_horse_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    item_id = parts[1]
    quantity = int(parts[2])

    event = await horse_shop_service.get_current_event(session)
    if not event:
        await cb.answer("Лавка коня сейчас закрыта", show_alert=True)
        return

    from app.services.cooldown_service import cooldown_service
    lock_key = f"horse_shop_buy:{user.id}"
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Покупка уже обрабатывается", show_alert=True)
        return

    try:
        result = await horse_shop_service.buy(session, user, event, item_id, quantity)
        if not result["ok"]:
            await cb.answer(f"❌ {result['reason']}", show_alert=True)
            return

        await cb.answer(
            f"✅ Куплено {result['quantity']}× {result['name']} за {fmt_num(result['cost'])} NHCoin!",
            show_alert=True,
        )
        await cb_horse_item(cb, session, user)
    finally:
        await cooldown_service.release_lock(lock_key)
