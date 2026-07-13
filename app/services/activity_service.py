"""Личная активность игрока: Алея славы (всё время) и Зал славы (текущий патч).

Веса совпадают с action_map клановой войны за регион (app/services/clan/region.py),
но БЕЗ капа на количество — личная активность копится без ограничений.
"""
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

ACTIVITY_POINTS: dict[str, int] = {
    "train": 1,
    "attack_gang": 2,
    "attack_king": 3,
    "attack_fist": 4,
    "raid": 3,
    "recruit": 1,
    "auction": 2,
    "duel": 3,
    "market": 1,
    "campaign": 4,
    "boss": 3,
    "quest": 2,
    "bank": 1,
}


async def record(session: AsyncSession, user_id: int, action: str) -> None:
    """Начисляет очки Алеи/Зала славы за размеченное игровое действие.

    Безопасно вызывать для любого игрока — не требует клана/войны.
    """
    pts = ACTIVITY_POINTS.get(action)
    if not pts:
        return

    # Слава — Гапрена «Лидер»: +50% очков активности
    has_leader = await session.scalar(
        select(User.fame_gaprena_leader).where(User.id == user_id)
    )
    if has_leader:
        pts = int(pts * 1.5)

    await session.execute(
        sa_update(User).where(User.id == user_id).values(
            fame_alltime_points=User.fame_alltime_points + pts,
            fame_patch_points=User.fame_patch_points + pts,
        )
    )
