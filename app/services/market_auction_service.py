"""Аукционы на бирже: продавец задаёт мин. ставку и время, комиссия системы 10%."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.market import MarketAuction, MarketAuctionBid
from app.constants.market import (
    ITEM_TYPES, MARKET_AUCTION_COMMISSION_PCT, MARKET_AUCTION_MIN_BID_INCREMENT_PCT,
    MARKET_AUCTION_DURATION_OPTIONS, MARKET_AUCTION_SOFT_CLOSE_SECONDS,
    MARKET_AUCTION_EXTEND_SECONDS, MARKET_AUCTION_MAX_PER_USER,
)
from app.services.market_service import market_service
from app.services.bank.casino.common import CASINO_RESOURCES, get_balance, set_balance


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_until(ends_at: datetime) -> float:
    """Разница в секундах до ends_at. Устойчиво к naive datetime (SQLite не всегда
    сохраняет tzinfo у TIMESTAMPTZ — в проде на Postgres ends_at всегда aware)."""
    now = _now() if ends_at.tzinfo else datetime.utcnow()
    return (ends_at - now).total_seconds()


class MarketAuctionService:

    async def get_active_auctions(
        self, session: AsyncSession, item_type: str | None = None,
        exclude_seller: int | None = None, limit: int = 20, offset: int = 0
    ) -> list[MarketAuction]:
        q = select(MarketAuction).where(
            MarketAuction.is_finished == False,
            MarketAuction.is_cancelled == False,
        )
        if item_type:
            q = q.where(MarketAuction.item_type == item_type)
        if exclude_seller:
            q = q.where(MarketAuction.seller_id != exclude_seller)
        q = q.order_by(MarketAuction.ends_at.asc()).offset(offset).limit(limit)
        result = await session.execute(q)
        return result.scalars().all()

    async def get_my_auctions(self, session: AsyncSession, seller_id: int) -> list[MarketAuction]:
        result = await session.execute(
            select(MarketAuction).where(
                MarketAuction.seller_id == seller_id,
                MarketAuction.is_finished == False,
                MarketAuction.is_cancelled == False,
            ).order_by(MarketAuction.created_at.desc())
        )
        return result.scalars().all()

    async def create_auction(
        self, session: AsyncSession, user: User, item_type: str, amount: int,
        meta: dict | None, resource: str, min_bid: int, duration_seconds: int,
    ) -> dict:
        if item_type not in ITEM_TYPES:
            return {"ok": False, "reason": "Неизвестный тип товара"}
        if amount <= 0:
            return {"ok": False, "reason": "Количество должно быть больше 0"}
        if resource not in CASINO_RESOURCES:
            return {"ok": False, "reason": "Неизвестный ресурс оплаты"}
        if min_bid <= 0:
            return {"ok": False, "reason": "Минимальная ставка должна быть больше 0"}
        if duration_seconds not in MARKET_AUCTION_DURATION_OPTIONS:
            return {"ok": False, "reason": "Некорректная длительность"}

        locked_user = await session.scalar(
            select(User).where(User.id == user.id).with_for_update()
        )
        if not locked_user:
            return {"ok": False, "reason": "Пользователь не найден"}

        count = await session.scalar(
            select(func.count(MarketAuction.id)).where(
                MarketAuction.seller_id == locked_user.id,
                MarketAuction.is_finished == False,
                MarketAuction.is_cancelled == False,
            )
        ) or 0
        if count >= MARKET_AUCTION_MAX_PER_USER:
            return {"ok": False, "reason": f"Максимум {MARKET_AUCTION_MAX_PER_USER} активных аукционов"}

        if meta is None:
            meta = {}

        take_result = await market_service.take_resource(session, locked_user, item_type, amount, meta)
        if not take_result["ok"]:
            return take_result

        auction = MarketAuction(
            seller_id=locked_user.id,
            item_type=item_type,
            item_amount=amount,
            item_meta=json.dumps(meta) if meta else None,
            resource=resource,
            min_bid=min_bid,
            ends_at=_now() + timedelta(seconds=duration_seconds),
        )
        session.add(auction)
        await session.flush()

        return {"ok": True, "auction_id": auction.id}

    async def cancel_auction(self, session: AsyncSession, user: User, auction_id: int) -> dict:
        result = await session.execute(
            select(MarketAuction).where(
                MarketAuction.id == auction_id,
                MarketAuction.seller_id == user.id,
                MarketAuction.is_finished == False,
                MarketAuction.is_cancelled == False,
            ).with_for_update()
        )
        auction = result.scalar_one_or_none()
        if not auction:
            return {"ok": False, "reason": "Аукцион не найден"}
        if auction.current_bid > 0:
            return {"ok": False, "reason": "Нельзя отменить — уже есть ставки"}

        auction.is_cancelled = True

        locked_user = await session.scalar(
            select(User).where(User.id == user.id).with_for_update()
        )
        if locked_user:
            meta = json.loads(auction.item_meta) if auction.item_meta else {}
            await market_service.give_resource(session, locked_user, auction.item_type, auction.item_amount, meta)
        await session.flush()
        return {"ok": True}

    def min_next_bid(self, auction: MarketAuction) -> int:
        if auction.current_bid <= 0:
            return auction.min_bid
        increment = max(1, int(auction.current_bid * MARKET_AUCTION_MIN_BID_INCREMENT_PCT))
        return auction.current_bid + increment

    async def place_bid(self, session: AsyncSession, user: User, auction_id: int, amount: int) -> dict:
        result = await session.execute(
            select(MarketAuction).where(MarketAuction.id == auction_id).with_for_update()
        )
        auction = result.scalar_one_or_none()
        if not auction or auction.is_finished or auction.is_cancelled:
            return {"ok": False, "reason": "Аукцион недоступен"}
        if _seconds_until(auction.ends_at) <= 0:
            return {"ok": False, "reason": "Время аукциона истекло"}
        if auction.seller_id == user.id:
            return {"ok": False, "reason": "Нельзя делать ставку на свой лот"}

        min_next = self.min_next_bid(auction)
        if amount < min_next:
            return {"ok": False, "reason": f"Минимальная ставка — {min_next:,}"}

        locked_bidder = await session.scalar(
            select(User).where(User.id == user.id).with_for_update()
        )
        if not locked_bidder:
            return {"ok": False, "reason": "Пользователь не найден"}

        balance = get_balance(locked_bidder, auction.resource)
        if balance < amount:
            return {"ok": False, "reason": f"Недостаточно {CASINO_RESOURCES.get(auction.resource, auction.resource)}"}

        # эскроу — списываем ставку у нового бидера сразу
        set_balance(locked_bidder, auction.resource, balance - amount)

        # возвращаем эскроу предыдущему лидеру (если был)
        if auction.high_bidder_id:
            prev_bidder = await session.scalar(
                select(User).where(User.id == auction.high_bidder_id).with_for_update()
            )
            if prev_bidder:
                set_balance(
                    prev_bidder, auction.resource,
                    get_balance(prev_bidder, auction.resource) + auction.current_bid,
                )

        auction.current_bid = amount
        auction.high_bidder_id = user.id

        # анти-снайп: продлеваем, если ставка сделана в последние N секунд
        remaining = _seconds_until(auction.ends_at)
        if remaining < MARKET_AUCTION_SOFT_CLOSE_SECONDS:
            auction.ends_at = auction.ends_at + timedelta(seconds=MARKET_AUCTION_EXTEND_SECONDS)

        session.add(MarketAuctionBid(auction_id=auction.id, user_id=user.id, amount=amount))
        await session.flush()

        return {"ok": True, "current_bid": amount, "ends_at": auction.ends_at, "resource": auction.resource}

    async def get_expired_auction_ids(self, session: AsyncSession) -> list[int]:
        result = await session.execute(
            select(MarketAuction.id).where(
                MarketAuction.is_finished == False,
                MarketAuction.is_cancelled == False,
                MarketAuction.ends_at <= _now(),
            )
        )
        return list(result.scalars().all())

    async def resolve_expired_by_id(self, session: AsyncSession, auction_id: int) -> dict | None:
        """Перечитывает лот под блокировкой и разрешает его, если он всё ещё истёк.

        Между фазой сбора ID и фазой разрешения ставка могла продлить ends_at
        (анти-снайп) — в этом случае просто пропускаем, следующий тик подхватит.
        """
        result = await session.execute(
            select(MarketAuction).where(MarketAuction.id == auction_id).with_for_update()
        )
        auction = result.scalar_one_or_none()
        if not auction or auction.is_finished or auction.is_cancelled:
            return None
        if _seconds_until(auction.ends_at) > 0:
            return None
        return await self.resolve_expired(session, auction)

    async def resolve_expired(self, session: AsyncSession, auction: MarketAuction) -> dict:
        """Разрешает один истёкший аукцион — вызывается тиком в отдельной транзакции на лот."""
        meta = json.loads(auction.item_meta) if auction.item_meta else {}
        label = ITEM_TYPES.get(auction.item_type, auction.item_type)

        if not auction.high_bidder_id or auction.current_bid <= 0:
            seller = await session.scalar(
                select(User).where(User.id == auction.seller_id).with_for_update()
            )
            if seller:
                await market_service.give_resource(session, seller, auction.item_type, auction.item_amount, meta)
            auction.is_finished = True
            auction.finished_at = _now()
            await session.flush()
            return {"event": "no_bids", "auction": auction, "item_label": label, "seller": seller}

        winner = await session.scalar(
            select(User).where(User.id == auction.high_bidder_id).with_for_update()
        )
        seller = await session.scalar(
            select(User).where(User.id == auction.seller_id).with_for_update()
        )

        if winner:
            await market_service.give_resource(session, winner, auction.item_type, auction.item_amount, meta)

        commission = int(auction.current_bid * MARKET_AUCTION_COMMISSION_PCT)
        payout = auction.current_bid - commission
        if seller:
            set_balance(seller, auction.resource, get_balance(seller, auction.resource) + payout)

        auction.is_finished = True
        auction.finished_at = _now()
        await session.flush()

        return {
            "event": "won", "auction": auction, "item_label": label,
            "winner": winner, "seller": seller,
            "amount": auction.item_amount, "price": payout, "resource": auction.resource,
        }


market_auction_service = MarketAuctionService()
