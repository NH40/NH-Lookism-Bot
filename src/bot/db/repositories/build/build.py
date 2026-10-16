"""Build — всё, что нужно для сборки бафов систем развития игрока, одним запросом
(репозиторий)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from bot.db.models.development import BattleMemory, UserGenius, UserPath, UserTechnique
from bot.db.models.user import User


_Path2 = aliased(UserPath)


@dataclass(frozen=True, slots=True)
class BuildRow:
    bloodline: str | None
    bloodline_level: int
    path: str | None
    path_level: int
    technique: str | None
    technique_level: int
    genius: str | None
    genius_level: int
    awakening_level: int
    mastery_speed: int = 0
    mastery_strength: int = 0
    # Второе тело (донат): второй путь и вторая родословная.
    path2: str | None = None
    path2_level: int = 0
    bloodline2: str | None = None
    bloodline2_level: int = 0


async def get_row(session: AsyncSession, user_id: int) -> BuildRow | None:
    """Пользователь + уровни активных пути/УТ/гениальности — одним запросом с LEFT JOIN."""
    row = (
        await session.execute(
            select(
                User.bloodline, User.bloodline_level,
                User.active_path, UserPath.level,
                User.active_technique, UserTechnique.level,
                User.active_genius, UserGenius.level,
                User.awakening_level,
                User.mastery_speed,
                User.mastery_strength,
                User.second_body, User.active_path2, _Path2.level, User.bloodline2, User.bloodline2_level,
            )
            .outerjoin(UserPath, (UserPath.user_id == User.id) & (UserPath.code == User.active_path))
            .outerjoin(UserTechnique, (UserTechnique.user_id == User.id) & (UserTechnique.code == User.active_technique))
            .outerjoin(UserGenius, (UserGenius.user_id == User.id) & (UserGenius.code == User.active_genius))
            .outerjoin(_Path2, (_Path2.user_id == User.id) & (_Path2.code == User.active_path2))
            .where(User.id == user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    bl, bll, p, pl, t, tl, g, gl, aw, msp, mst, body, p2, p2l, bl2, bl2l = row
    if not body:
        p2 = p2l = bl2 = bl2l = None
    return BuildRow(
        bloodline=bl, bloodline_level=bll or 0,
        path=p if pl else None, path_level=pl or 0,
        technique=t if tl else None, technique_level=tl or 0,
        genius=g if gl else None, genius_level=gl or 0,
        awakening_level=aw or 0,
        mastery_speed=msp or 0,
        mastery_strength=mst or 0,
        path2=p2 if p2l else None, path2_level=p2l or 0,
        bloodline2=bl2, bloodline2_level=bl2l or 0,
    )


async def list_memory(session: AsyncSession, user_id: int, limit: int) -> Sequence[tuple[str, int]]:
    """Пути последних противников, свежие первыми."""
    rows = await session.execute(
        select(BattleMemory.path_code, BattleMemory.path_level)
        .where(BattleMemory.user_id == user_id)
        .order_by(BattleMemory.fought_at.desc(), BattleMemory.id.desc())
        .limit(limit)
    )
    return [(r[0], r[1]) for r in rows.all()]
