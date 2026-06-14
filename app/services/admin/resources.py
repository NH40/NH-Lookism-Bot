from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class AdminResourcesMixin:

    async def give_mastery_points(self, session: AsyncSession, user: User, amount: int) -> None:
        user.mastery_points += amount
        await session.flush()

    async def give_path_points(self, session: AsyncSession, user: User, amount: int) -> None:
        user.skill_path_points += amount
        await session.flush()

    async def give_ui_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.ui_fragments += amount
        await session.flush()

    async def give_alchemy_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.alchemy_fragments = getattr(user, "alchemy_fragments", 0) + amount
        await session.flush()

    async def give_path_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.path_fragments = getattr(user, "path_fragments", 0) + amount
        await session.flush()

    async def give_business_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.business_fragments = getattr(user, "business_fragments", 0) + amount
        await session.flush()

    async def give_war_points(self, session: AsyncSession, user: User, amount: int) -> None:
        user.war_points = getattr(user, "war_points", 0) + amount
        await session.flush()

    async def give_activity_points(self, session: AsyncSession, user: User, amount: int) -> dict:
        from app.models.clan import ClanMember
        from app.models.clan_region import KoreanRegionWar, KoreanRegionWarParticipant
        from datetime import datetime, timezone

        user.activity_points = (user.activity_points or 0) + amount
        await session.flush()

        clan_member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user.id)
        )
        if not clan_member:
            return {"ok": True, "war_updated": False}

        now = datetime.now(timezone.utc)
        participant = await session.scalar(
            select(KoreanRegionWarParticipant)
            .join(KoreanRegionWar, KoreanRegionWar.id == KoreanRegionWarParticipant.war_id)
            .where(
                KoreanRegionWarParticipant.clan_id == clan_member.clan_id,
                KoreanRegionWar.is_finished == False,
                KoreanRegionWar.ends_at > now,
            )
        )
        if participant:
            participant.score += amount
            await session.flush()
            return {"ok": True, "war_updated": True}

        return {"ok": True, "war_updated": False}

    async def give_donate(self, session: AsyncSession, user: User, amount: int) -> None:
        user.nh_donate = getattr(user, "nh_donate", 0) + amount
        await session.flush()

    async def give_squad_member(self, session: AsyncSession, user: User, rank: str, count: int = 1) -> dict:
        from app.data.squad import RANKS_BY_ID
        from app.models.squad_member import SquadMember

        rank_cfg = RANKS_BY_ID.get(rank)
        if not rank_cfg:
            return {"ok": False, "reason": "Ранг не найден"}

        for _ in range(count):
            member = SquadMember(
                user_id=user.id,
                rank=rank,
                stars=0,
                base_power=rank_cfg.base_power,
            )
            session.add(member)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "rank": rank, "count": count}
