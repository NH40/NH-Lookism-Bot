from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.horse_shop import HorseShopEvent
from app.config.game_balance import HORSE_SHOP_ITEMS, HORSE_SHOP_MAX_PER_ITEM
from app.repositories.horse_shop_repo import horse_shop_repo


class HorseShopService:

    async def get_current_event(self, session: AsyncSession) -> HorseShopEvent | None:
        return await horse_shop_repo.get_current_event(session)

    async def buy(
        self, session: AsyncSession, user: User, event: HorseShopEvent,
        item_id: str, quantity: int,
    ) -> dict:
        if quantity <= 0:
            return {"ok": False, "reason": "Количество должно быть больше 0"}

        cfg = HORSE_SHOP_ITEMS.get(item_id)
        if not cfg:
            return {"ok": False, "reason": "Товар не найден"}

        purchase = await horse_shop_repo.get_or_create_purchase(session, event.id, user.id, item_id)
        remaining = HORSE_SHOP_MAX_PER_ITEM - purchase.quantity
        if remaining <= 0:
            return {"ok": False, "reason": f"Лимит уже достигнут ({HORSE_SHOP_MAX_PER_ITEM}/{HORSE_SHOP_MAX_PER_ITEM})"}
        if quantity > remaining:
            return {"ok": False, "reason": f"Можно купить ещё максимум {remaining} шт."}

        cost = cfg["price"] * quantity
        if user.nh_coins < cost:
            return {"ok": False, "reason": f"Недостаточно NHCoin (нужно {cost:,})"}

        user.nh_coins -= cost
        setattr(user, cfg["field"], (getattr(user, cfg["field"], 0) or 0) + quantity)
        purchase.quantity += quantity
        await session.flush()

        return {
            "ok": True,
            "item_id": item_id,
            "name": cfg["name"],
            "quantity": quantity,
            "cost": cost,
            "total_bought": purchase.quantity,
        }


horse_shop_service = HorseShopService()
