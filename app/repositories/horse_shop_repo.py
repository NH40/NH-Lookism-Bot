from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.horse_shop import HorseShopEvent, HorseShopPurchase


class HorseShopRepo:

    # ── HorseShopEvent ───────────────────────────────────────────────────────

    async def get_current_event(self, session: AsyncSession) -> HorseShopEvent | None:
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(HorseShopEvent).where(
                HorseShopEvent.status == "active",
                HorseShopEvent.expires_at > now,
            )
        )

    async def get_current_event_for_update(self, session: AsyncSession) -> HorseShopEvent | None:
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(HorseShopEvent).where(
                HorseShopEvent.status == "active",
                HorseShopEvent.expires_at > now,
            ).with_for_update()
        )

    async def get_expired_active(self, session: AsyncSession) -> HorseShopEvent | None:
        now = datetime.now(timezone.utc)
        return await session.scalar(
            select(HorseShopEvent).where(
                HorseShopEvent.status == "active",
                HorseShopEvent.expires_at <= now,
            )
        )

    async def get_last_event(self, session: AsyncSession) -> HorseShopEvent | None:
        return await session.scalar(
            select(HorseShopEvent)
            .where(HorseShopEvent.status != "active")
            .order_by(desc(HorseShopEvent.id))
            .limit(1)
        )

    async def get_pending_spawn(self, session: AsyncSession) -> HorseShopEvent | None:
        now = datetime.now(timezone.utc)
        last = await session.scalar(
            select(HorseShopEvent)
            .where(HorseShopEvent.status != "active")
            .order_by(desc(HorseShopEvent.id))
            .limit(1)
        )
        if last and last.next_spawn_at and last.next_spawn_at <= now:
            return last
        return None

    async def create_event(
        self, session: AsyncSession, started_at: datetime, expires_at: datetime,
    ) -> HorseShopEvent:
        event = HorseShopEvent(status="active", started_at=started_at, expires_at=expires_at)
        session.add(event)
        await session.flush()
        return event

    async def finish_event(
        self, session: AsyncSession, event: HorseShopEvent, next_spawn_at: datetime,
    ) -> None:
        event.status = "expired"
        event.next_spawn_at = next_spawn_at
        await session.flush()

    # ── HorseShopPurchase ────────────────────────────────────────────────────

    async def get_or_create_purchase(
        self, session: AsyncSession, event_id: int, user_id: int, item_id: str,
    ) -> HorseShopPurchase:
        rec = await session.scalar(
            select(HorseShopPurchase).where(
                HorseShopPurchase.event_id == event_id,
                HorseShopPurchase.user_id == user_id,
                HorseShopPurchase.item_id == item_id,
            )
        )
        if rec:
            return rec
        rec = HorseShopPurchase(event_id=event_id, user_id=user_id, item_id=item_id, quantity=0)
        session.add(rec)
        await session.flush()
        return rec

    async def get_user_purchases(
        self, session: AsyncSession, event_id: int, user_id: int,
    ) -> dict[str, int]:
        result = await session.execute(
            select(HorseShopPurchase.item_id, HorseShopPurchase.quantity).where(
                HorseShopPurchase.event_id == event_id,
                HorseShopPurchase.user_id == user_id,
            )
        )
        return {item_id: qty for item_id, qty in result.all()}


horse_shop_repo = HorseShopRepo()
