"""Уведомления о покупке/продаже на бирже (по образцу notify_pvp_attack)."""
from app.models.user import User
from app.services.bank.casino.common import CASINO_RESOURCES
from app.utils.formatters import fmt_num


async def notify_market_sale(seller: User, item_label: str, amount: int, price: int, resource: str) -> None:
    """Уведомляет продавца, что его товар куплен."""
    if not seller.notifications_enabled or not getattr(seller, "notif_market_sell", True):
        return
    try:
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        await bot.send_message(
            seller.tg_id,
            f"💰 <b>Продажа!</b>\n\n{item_label} x{amount}\n"
            f"Получено: {fmt_num(price)} {CASINO_RESOURCES.get(resource, resource)}",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def notify_market_purchase(buyer: User, item_label: str, amount: int, price: int, resource: str) -> None:
    """Подтверждение покупателю (в дополнение к мгновенному cb.answer)."""
    if not buyer.notifications_enabled or not getattr(buyer, "notif_market_buy", True):
        return
    try:
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        await bot.send_message(
            buyer.tg_id,
            f"✅ <b>Покупка!</b>\n\n{item_label} x{amount}\n"
            f"Заплачено: {fmt_num(price)} {CASINO_RESOURCES.get(resource, resource)}",
            parse_mode="HTML",
        )
    except Exception:
        pass
