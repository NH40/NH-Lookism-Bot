"""Хелпер для записи личной активности игрока (Алея/Зал славы)."""
from sqlalchemy.ext.asyncio import AsyncSession


async def record(session: AsyncSession, user_id: int, action: str) -> None:
    """Безопасно вызывать из любого хендлера — молча игнорирует ошибки."""
    from app.services.activity_service import record as record_fame
    try:
        await record_fame(session, user_id, action)
    except Exception:
        pass
