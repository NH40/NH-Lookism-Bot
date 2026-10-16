"""Промокоды (репозиторий). Листовые функции НЕ коммитят — коммит у сервиса."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.promo import PromoCode, PromoRedemption


async def get_by_code(session: AsyncSession, code: str) -> PromoCode | None:
    return await session.scalar(select(PromoCode).where(PromoCode.code == code))


async def get(session: AsyncSession, promo_id: int) -> PromoCode | None:
    return await session.get(PromoCode, promo_id)


async def add(
    session: AsyncSession,
    *,
    code: str,
    reward: dict,
    max_uses: int | None,
    expires_at: datetime | None,
    allowed_usernames: list[str] | None,
    created_by: int,
) -> PromoCode:
    promo = PromoCode(
        code=code, reward=reward, max_uses=max_uses, expires_at=expires_at,
        allowed_usernames=allowed_usernames, created_by=created_by,
    )
    session.add(promo)
    await session.flush()
    return promo


async def list_recent(session: AsyncSession, limit: int) -> list[PromoCode]:
    rows = await session.scalars(select(PromoCode).order_by(PromoCode.id.desc()).limit(limit))
    return list(rows)


async def set_active(session: AsyncSession, promo_id: int, active: bool) -> bool:
    result = await session.execute(update(PromoCode).where(PromoCode.id == promo_id).values(is_active=active))
    return result.rowcount > 0


async def delete_promo(session: AsyncSession, promo_id: int) -> bool:
    result = await session.execute(delete(PromoCode).where(PromoCode.id == promo_id))
    return result.rowcount > 0


async def insert_redemption(session: AsyncSession, promo_id: int, user_id: int) -> bool:
    """True — активация записана, False — игрок уже активировал этот код."""
    row = await session.execute(
        insert(PromoRedemption).values(promo_id=promo_id, user_id=user_id)
        .on_conflict_do_nothing().returning(PromoRedemption.promo_id)
    )
    return row.first() is not None


async def increment_used(session: AsyncSession, promo_id: int) -> bool:
    """Атомарный инкремент с проверкой лимита в самом UPDATE. False — лимит исчерпан."""
    row = await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id, (PromoCode.max_uses.is_(None)) | (PromoCode.used_count < PromoCode.max_uses))
        .values(used_count=PromoCode.used_count + 1)
        .returning(PromoCode.id)
    )
    return row.first() is not None
