import json
from datetime import datetime, timezone
from app.constants.market import ITEM_TYPES, MAX_LISTINGS_PER_USER
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.models.user import User
from app.models.market import MarketListing


class MarketService:

    def get_item_label(self, item_type: str) -> str:
        return ITEM_TYPES.get(item_type, item_type)

    async def get_active_listings(
        self, session: AsyncSession, item_type: str | None = None,
        exclude_seller: int | None = None, limit: int = 20, offset: int = 0
    ) -> list[MarketListing]:
        q = select(MarketListing).where(
            MarketListing.is_sold == False,
            MarketListing.is_cancelled == False,
        )
        if item_type:
            q = q.where(MarketListing.item_type == item_type)
        if exclude_seller:
            q = q.where(MarketListing.seller_id != exclude_seller)
        q = q.order_by(MarketListing.price.asc()).offset(offset).limit(limit)
        result = await session.execute(q)
        return result.scalars().all()

    async def get_my_listings(
        self, session: AsyncSession, seller_id: int
    ) -> list[MarketListing]:
        result = await session.execute(
            select(MarketListing).where(
                MarketListing.seller_id == seller_id,
                MarketListing.is_sold == False,
                MarketListing.is_cancelled == False,
            ).order_by(MarketListing.created_at.desc())
        )
        return result.scalars().all()

    async def create_listing(
        self, session: AsyncSession, user: User,
        item_type: str, amount: int, price: int, meta: dict | None = None
    ) -> dict:
        if item_type not in ITEM_TYPES:
            return {"ok": False, "reason": "Неизвестный тип товара"}
        if amount <= 0:
            return {"ok": False, "reason": "Количество должно быть больше 0"}
        if price <= 0:
            return {"ok": False, "reason": "Цена должна быть больше 0"}

        count = await session.scalar(
            select(func.count(MarketListing.id)).where(
                MarketListing.seller_id == user.id,
                MarketListing.is_sold == False,
                MarketListing.is_cancelled == False,
            )
        ) or 0
        if count >= MAX_LISTINGS_PER_USER:
            return {"ok": False, "reason": f"Максимум {MAX_LISTINGS_PER_USER} активных товаров"}

        if meta is None:
            meta = {}

        take_result = await self._take_resource(session, user, item_type, amount, meta)
        if not take_result["ok"]:
            return take_result

        listing = MarketListing(
            seller_id=user.id,
            item_type=item_type,
            item_amount=amount,
            price=price,
            item_meta=json.dumps(meta) if meta else None,
        )
        session.add(listing)
        await session.flush()

        return {"ok": True, "listing_id": listing.id}

    async def cancel_all_user_listings(
        self, session: AsyncSession, user_id: int
    ) -> None:
        """Отменяет все активные лоты пользователя без возврата ресурсов."""
        await session.execute(
            update(MarketListing)
            .where(
                MarketListing.seller_id == user_id,
                MarketListing.is_sold == False,
                MarketListing.is_cancelled == False,
            )
            .values(is_cancelled=True)
        )

    async def cancel_listing(
        self, session: AsyncSession, user: User, listing_id: int
    ) -> dict:
        result = await session.execute(
            select(MarketListing).where(
                MarketListing.id == listing_id,
                MarketListing.seller_id == user.id,
                MarketListing.is_sold == False,
                MarketListing.is_cancelled == False,
            )
        )
        listing = result.scalar_one_or_none()
        if not listing:
            return {"ok": False, "reason": "Товар не найден"}

        listing.is_cancelled = True
        meta = json.loads(listing.item_meta) if listing.item_meta else {}
        await self._give_resource(session, user, listing.item_type, listing.item_amount, meta)
        await session.flush()

        return {"ok": True}

    async def buy_listing(
        self, session: AsyncSession, buyer: User, listing_id: int
    ) -> dict:
        result = await session.execute(
            select(MarketListing).where(
                MarketListing.id == listing_id,
                MarketListing.is_sold == False,
                MarketListing.is_cancelled == False,
            )
        )
        listing = result.scalar_one_or_none()
        if not listing:
            return {"ok": False, "reason": "Товар уже куплен или не найден"}
        if listing.seller_id == buyer.id:
            return {"ok": False, "reason": "Нельзя купить свой товар"}
        if buyer.nh_coins < listing.price:
            return {"ok": False, "reason": f"Недостаточно NHCoin (нужно {listing.price:,})"}

        buyer.nh_coins -= listing.price

        from app.repositories.user_repo import user_repo
        seller = await user_repo.get_by_id(session, listing.seller_id)
        if seller:
            seller.nh_coins += listing.price

        meta = json.loads(listing.item_meta) if listing.item_meta else {}
        await self._give_resource(session, buyer, listing.item_type, listing.item_amount, meta)

        listing.is_sold = True
        listing.buyer_id = buyer.id
        listing.sold_at = datetime.now(timezone.utc)
        await session.flush()

        return {
            "ok": True,
            "item_type": listing.item_type,
            "amount": listing.item_amount,
            "price": listing.price,
        }

    async def _take_resource(
        self, session: AsyncSession, user: User,
        item_type: str, amount: int, meta: dict
    ) -> dict:
        if item_type == "tickets":
            if user.tickets < amount:
                return {"ok": False, "reason": f"Недостаточно тикетов (есть {user.tickets})"}
            user.tickets -= amount

        elif item_type == "path_points":
            if user.skill_path_points < amount:
                return {"ok": False, "reason": f"Недостаточно очков пути (есть {user.skill_path_points})"}
            user.skill_path_points -= amount

        elif item_type == "mastery_points":
            if user.mastery_points < amount:
                return {"ok": False, "reason": f"Недостаточно очков мастерства (есть {user.mastery_points})"}
            user.mastery_points -= amount

        elif item_type == "ui_fragments":
            if user.ui_fragments < amount:
                return {"ok": False, "reason": f"Недостаточно фрагментов УИ (есть {user.ui_fragments})"}
            user.ui_fragments -= amount

        elif item_type == "squad_member":
            from app.models.squad_member import SquadMember
            rank = meta.get("rank") if meta else None
            q = select(SquadMember).where(SquadMember.user_id == user.id)
            if rank:
                q = q.where(SquadMember.rank == rank)
            q = q.limit(amount)
            result = await session.execute(q)
            members = result.scalars().all()
            if len(members) < amount:
                return {"ok": False, "reason": f"Недостаточно статистов (есть {len(members)})"}
            avg_power = int(sum(m.base_power for m in members) / len(members)) if members else 1000
            meta["power"] = avg_power
            for m in members:
                await session.delete(m)
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, user)

        elif item_type == "character":
            from app.models.character import UserCharacter
            char_id = meta.get("char_id")
            rank = meta.get("rank")
            if not char_id:
                return {"ok": False, "reason": "Не указан персонаж"}
            q = select(UserCharacter).where(
                UserCharacter.user_id == user.id,
                UserCharacter.character_id == char_id,
            )
            if rank:
                q = q.where(UserCharacter.rank == rank)
            q = q.limit(amount)
            result = await session.execute(q)
            chars = result.scalars().all()
            if len(chars) < amount:
                return {"ok": False, "reason": f"Недостаточно персонажей (есть {len(chars)})"}
            avg_power = int(sum(c.power for c in chars) / len(chars)) if chars else 0
            meta["power"] = avg_power
            for c in chars:
                await session.delete(c)
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, user)

        await session.flush()
        return {"ok": True}

    async def _give_resource(
        self, session: AsyncSession, user: User,
        item_type: str, amount: int, meta: dict
    ) -> None:
        if item_type == "tickets":
            user.tickets += amount

        elif item_type == "path_points":
            user.skill_path_points += amount

        elif item_type == "mastery_points":
            user.mastery_points += amount

        elif item_type == "ui_fragments":
            user.ui_fragments += amount

        elif item_type == "squad_member":
            from app.models.squad_member import SquadMember
            rank = meta.get("rank", "C")
            power = meta.get("power", 1000)
            for _ in range(amount):
                session.add(SquadMember(
                    user_id=user.id,
                    rank=rank,
                    base_power=power,
                ))
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, user)

        elif item_type == "character":
            from app.models.character import UserCharacter
            char_id = meta.get("char_id")
            power = meta.get("power", 0)
            rank = meta.get("rank", "C")
            if char_id:
                for _ in range(amount):
                    session.add(UserCharacter(
                        user_id=user.id,
                        character_id=char_id,
                        rank=rank,
                        power=power,
                    ))
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, user)

        await session.flush()


market_service = MarketService()