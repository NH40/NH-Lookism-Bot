"""Реферальные кампании админа (сервис)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.referral import REF_ACTIVE_DAYS, REF_CODE_BYTES, REF_LIST_LIMIT, REF_START_PREFIX
from bot.db.models.referral import ReferralLink
from bot.db.repositories import referral as referral_repo
from bot.services.admin import audit


def deep_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={REF_START_PREFIX}{code}"


async def create_campaign(session: AsyncSession, admin_id: int, name: str) -> ReferralLink:
    link = await referral_repo.add(session, code=secrets.token_hex(REF_CODE_BYTES), name=name, created_by=admin_id)
    await audit.log(session, admin_id, "ref_create", None, {"code": link.code, "name": name})
    await session.commit()
    return link


async def list_campaigns(session: AsyncSession) -> list[tuple[ReferralLink, int]]:
    return await referral_repo.list_with_counts(session, REF_LIST_LIMIT)


async def get_campaign(session: AsyncSession, link_id: int) -> ReferralLink | None:
    return await referral_repo.get(session, link_id)


async def stats(session: AsyncSession, link_id: int) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(days=REF_ACTIVE_DAYS)
    return await referral_repo.campaign_stats(session, link_id, since)


async def delete_campaign(session: AsyncSession, admin_id: int, link_id: int) -> bool:
    link = await referral_repo.get(session, link_id)
    if link is None:
        return False
    await audit.log(session, admin_id, "ref_delete", None, {"code": link.code, "name": link.name})
    await referral_repo.delete_link(session, link_id)
    await session.commit()
    return True


async def record_visit(session: AsyncSession, user_id: int, payload: str) -> bool:
    """`/start ref_<code>` НОВОГО игрока: привязать к кампании. Коммитит. False — не наш
    payload или кампании нет."""
    if not payload.startswith(REF_START_PREFIX):
        return False
    link = await referral_repo.get_by_code(session, payload.removeprefix(REF_START_PREFIX))
    if link is None:
        return False
    added = await referral_repo.add_visit(session, user_id, link.id)
    await session.commit()
    return added
