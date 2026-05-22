from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.user import User
from app.models.title import UserDonatTitle
from app.data.titles import DONAT_TITLES, DONAT_SETS


async def grant_all_titles(
    session: AsyncSession,
    user: User,
    admin_tg_id: int,
    grant_fn,
) -> int:
    """Grant every donat title. grant_fn is TitleService.grant_title."""
    count = 0
    for title in DONAT_TITLES:
        result = await grant_fn(session, user, title.title_id, admin_tg_id)
        if result["ok"]:
            count += 1
    return count


async def revoke_set(
    session: AsyncSession,
    user: User,
    set_id: str,
    reapply_fn,
) -> int:
    """Remove all titles in a set and reapply the rest."""
    ids = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
    result = await session.execute(
        delete(UserDonatTitle).where(
            UserDonatTitle.user_id == user.id,
            UserDonatTitle.title_id.in_(ids),
        )
    )
    removed = result.rowcount
    await session.flush()
    await reapply_fn(session, user)
    return removed


async def revoke_all_titles(
    session: AsyncSession,
    user: User,
    reapply_fn,
) -> None:
    await session.execute(
        delete(UserDonatTitle).where(UserDonatTitle.user_id == user.id)
    )
    await session.flush()
    await reapply_fn(session, user)


async def has_set(
    session: AsyncSession, user_id: int, set_id: str
) -> bool:
    titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
    if not titles_in_set:
        return False
    result = await session.execute(
        select(UserDonatTitle.title_id).where(
            UserDonatTitle.user_id == user_id
        )
    )
    owned = set(result.scalars().all())
    return all(tid in owned for tid in titles_in_set)
