"""Реферальные кампании (репозиторий). НЕ коммитит — коммит у сервиса."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.battle_pass import BattlePass
from bot.db.models.donate import Payment
from bot.db.models.referral import ReferralLink, ReferralVisit
from bot.db.models.user import User


async def get_by_code(session: AsyncSession, code: str) -> ReferralLink | None:
    return await session.scalar(select(ReferralLink).where(ReferralLink.code == code))


async def get(session: AsyncSession, link_id: int) -> ReferralLink | None:
    return await session.get(ReferralLink, link_id)


async def add(session: AsyncSession, *, code: str, name: str, created_by: int) -> ReferralLink:
    link = ReferralLink(code=code, name=name, created_by=created_by)
    session.add(link)
    await session.flush()
    return link


async def list_with_counts(session: AsyncSession, limit: int) -> list[tuple[ReferralLink, int]]:
    rows = await session.execute(
        select(ReferralLink, func.count(ReferralVisit.user_id))
        .outerjoin(ReferralVisit, ReferralVisit.link_id == ReferralLink.id)
        .group_by(ReferralLink.id).order_by(ReferralLink.id.desc()).limit(limit)
    )
    return [(link, int(cnt)) for link, cnt in rows.all()]


async def delete_link(session: AsyncSession, link_id: int) -> bool:
    result = await session.execute(delete(ReferralLink).where(ReferralLink.id == link_id))
    return result.rowcount > 0


async def add_visit(session: AsyncSession, user_id: int, link_id: int) -> bool:
    row = await session.execute(
        insert(ReferralVisit).values(user_id=user_id, link_id=link_id)
        .on_conflict_do_nothing().returning(ReferralVisit.user_id)
    )
    return row.first() is not None


async def campaign_stats(session: AsyncSession, link_id: int, active_since: datetime) -> dict[str, int]:
    """Живая агрегация (несколько небольших запросов — экран открывает админ по кнопке)."""
    visitors = select(ReferralVisit.user_id).where(ReferralVisit.link_id == link_id)
    came = await session.scalar(select(func.count()).select_from(visitors.subquery())) or 0
    playing = await session.scalar(
        select(func.count()).select_from(User)
        .where(User.id.in_(visitors), User.last_active_at >= active_since)
    ) or 0
    donors, donated = (
        await session.execute(
            select(func.count(distinct(Payment.user_id)), func.coalesce(func.sum(Payment.amount_rub), 0))
            .where(Payment.user_id.in_(visitors))
        )
    ).one()
    bp = await session.scalar(
        select(func.count(distinct(BattlePass.user_id)))
        .where(BattlePass.user_id.in_(visitors), BattlePass.is_premium.is_(True))
    ) or 0
    return {"came": int(came), "playing": int(playing), "donors": int(donors), "donated": int(donated), "bp": int(bp)}
