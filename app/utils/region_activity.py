"""Хелпер для записи активности игрока в войне за регион."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def record(session: AsyncSession, user_id: int, action: str) -> None:
    """Записывает активность игрока если его клан участвует в войне за регион.

    Безопасно вызывать из любого хендлера — молча игнорирует если нет войны.
    """
    try:
        from app.models.clan import ClanMember
        from app.services.clan import clan_service
        clan_member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user_id)
        )
        if clan_member:
            await clan_service.record_activity(session, user_id, clan_member.clan_id, action)
    except Exception:
        pass
