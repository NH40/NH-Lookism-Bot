from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanMember, ClanInvite
from app.services.clan.base import ClanBaseService


class ClanInviteService(ClanBaseService):

    async def invite_user(self, session: AsyncSession, clan: Clan, from_user: User, to_username: str) -> dict:
        members = await self.get_clan_members(session, clan.id)
        if len(members) >= clan.max_members:
            return {"ok": False, "reason": f"Клан уже заполнен ({clan.max_members} чел.)"}
        to_user = await session.scalar(select(User).where(User.username == to_username.lstrip("@")))
        if not to_user:
            return {"ok": False, "reason": "Игрок не найден"}
        if to_user.id == from_user.id:
            return {"ok": False, "reason": "Нельзя пригласить себя"}
        existing_member = await session.scalar(select(ClanMember).where(ClanMember.user_id == to_user.id))
        if existing_member:
            return {"ok": False, "reason": "Игрок уже в клане"}
        existing_invite = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.clan_id == clan.id,
                ClanInvite.to_user_id == to_user.id,
                ClanInvite.is_pending == True,
            )
        )
        if existing_invite:
            return {"ok": False, "reason": "Приглашение уже отправлено"}
        invite = ClanInvite(clan_id=clan.id, from_user_id=from_user.id, to_user_id=to_user.id, invite_type="invite")
        session.add(invite)
        await session.flush()
        return {"ok": True, "invite_id": invite.id, "to_user": to_user}

    async def request_join(self, session: AsyncSession, clan: Clan, user: User) -> dict:
        existing_member = await session.scalar(select(ClanMember).where(ClanMember.user_id == user.id))
        if existing_member:
            return {"ok": False, "reason": "Вы уже состоите в клане"}
        members = await self.get_clan_members(session, clan.id)
        if len(members) >= clan.max_members:
            return {"ok": False, "reason": "Клан уже заполнен"}
        existing_request = await session.scalar(
            select(ClanInvite).where(ClanInvite.to_user_id == user.id, ClanInvite.is_pending == True)
        )
        if existing_request:
            return {"ok": False, "reason": "У вас уже есть активный запрос или приглашение"}
        request = ClanInvite(clan_id=clan.id, from_user_id=user.id, to_user_id=user.id, invite_type="request")
        session.add(request)
        await session.flush()
        return {"ok": True, "request_id": request.id}

    async def cancel_request(self, session: AsyncSession, user: User) -> dict:
        """Отмена своей заявки."""
        invite = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.to_user_id == user.id,
                ClanInvite.is_pending == True,
                ClanInvite.invite_type == "request",
            )
        )
        if not invite:
            return {"ok": False, "reason": "Активная заявка не найдена"}
        invite.is_pending = False
        await session.flush()
        return {"ok": True}

    async def accept_invite(self, session: AsyncSession, invite_id: int, user: User) -> dict:
        invite = await session.scalar(
            select(ClanInvite).where(ClanInvite.id == invite_id, ClanInvite.is_pending == True)
        )
        if not invite:
            return {"ok": False, "reason": "Приглашение не найдено или истекло"}
        existing = await session.scalar(select(ClanMember).where(ClanMember.user_id == user.id))
        if existing:
            invite.is_pending = False
            await session.flush()
            return {"ok": False, "reason": "Вы уже состоите в клане"}
        clan = await session.scalar(select(Clan).where(Clan.id == invite.clan_id))
        if not clan:
            return {"ok": False, "reason": "Клан не найден"}
        members = await self.get_clan_members(session, clan.id)
        if len(members) >= clan.max_members:
            invite.is_pending = False
            await session.flush()
            return {"ok": False, "reason": "Клан уже заполнен"}
        other_invites = await session.execute(
            select(ClanInvite).where(
                ClanInvite.to_user_id == user.id,
                ClanInvite.is_pending == True,
                ClanInvite.id != invite_id,
            )
        )
        for other in other_invites.scalars().all():
            other.is_pending = False
        invite.is_pending = False
        member = ClanMember(clan_id=clan.id, user_id=user.id)
        session.add(member)
        await self.recalc_power(session, clan)
        await self._add_clan_bonuses_to_user(session, clan, user)
        await session.flush()
        return {"ok": True, "clan": clan}

    async def decline_invite(self, session: AsyncSession, invite_id: int) -> dict:
        invite = await session.scalar(
            select(ClanInvite).where(ClanInvite.id == invite_id, ClanInvite.is_pending == True)
        )
        if not invite:
            return {"ok": False, "reason": "Приглашение не найдено"}
        invite.is_pending = False
        await session.flush()
        return {"ok": True}