"""DB-запросы для системы Походов."""
import json
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign


class CampaignRepo:

    async def get_active(self, session: AsyncSession, user_id: int) -> list[Campaign]:
        """Все активные (ещё не завершённые) походы игрока."""
        result = await session.execute(
            select(Campaign)
            .where(Campaign.user_id == user_id, Campaign.status == "active")
            .order_by(Campaign.ends_at)
        )
        return list(result.scalars().all())

    async def get_finished(self, session: AsyncSession, user_id: int) -> list[Campaign]:
        """Завершённые походы, которые ещё не забрал игрок."""
        result = await session.execute(
            select(Campaign)
            .where(Campaign.user_id == user_id, Campaign.status == "finished")
            .order_by(Campaign.ends_at)
        )
        return list(result.scalars().all())

    async def count_active(self, session: AsyncSession, user_id: int) -> int:
        """Количество активных походов."""
        val = await session.scalar(
            select(func.count(Campaign.id))
            .where(Campaign.user_id == user_id, Campaign.status == "active")
        )
        return val or 0

    async def get_by_id(self, session: AsyncSession, campaign_id: int) -> Campaign | None:
        return await session.get(Campaign, campaign_id)

    async def create(
        self,
        session: AsyncSession,
        user_id: int,
        resource_type: str,
        rank: str,
        duration_hours: int,
        statist_ids: list[int],
        avg_power: int,
        ends_at: datetime,
    ) -> Campaign:
        camp = Campaign(
            user_id=user_id,
            resource_type=resource_type,
            rank=rank,
            duration_hours=duration_hours,
            statist_ids=json.dumps(statist_ids),
            statist_count=len(statist_ids),
            avg_power=avg_power,
            ends_at=ends_at,
            status="active",
        )
        session.add(camp)
        await session.flush()
        return camp

    async def finish(
        self,
        session: AsyncSession,
        campaign: Campaign,
        success: bool,
        resource_gained: int,
        statists_returned: int,
        statists_lost: int,
    ) -> None:
        campaign.status = "finished"
        campaign.success = success
        campaign.resource_gained = resource_gained
        campaign.statists_returned = statists_returned
        campaign.statists_lost = statists_lost
        await session.flush()

    async def delete(self, session: AsyncSession, campaign: Campaign) -> None:
        await session.delete(campaign)
        await session.flush()

    # ── Планировщик: все активные походы, у которых истёк таймер ─────────────

    async def get_expired_active(self, session: AsyncSession) -> list[Campaign]:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Campaign)
            .where(Campaign.status == "active", Campaign.ends_at <= now)
        )
        return list(result.scalars().all())


campaign_repo = CampaignRepo()
