"""Админка «Сезон пасса и задания» (сервис). Мутации пишут аудит в той же транзакции."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.battle_pass import level_from_xp
from bot.constant.admin.season_admin import (
    AUDIT_SE_NEW_SEASON, AUDIT_SE_PREMIUM, AUDIT_SE_QUEST_DONE, AUDIT_SE_QUEST_REROLL, AUDIT_SE_RESET_CLAIMS,
    AUDIT_SE_XP, XP_LIMIT,
)
from bot.db.models.battle_pass import BattlePassClaim, BpSeason
from bot.db.models.quest import DailyQuest, DailyQuestState
from bot.db.repositories import battle_pass as bp_repo
from bot.db.repositories import quest as quest_repo
from bot.services.admin import audit
from bot.services.battle_pass import current_season
from bot.services.quest import QuestStatus, get_status, on_event, today


@dataclass(frozen=True, slots=True)
class SeasonInfo:
    season: BpSeason
    premium: int
    left_seconds: int


@dataclass(frozen=True, slots=True)
class PassInfo:
    season: BpSeason
    xp: int
    level: int
    premium: bool
    claimed_free: int
    claimed_premium: int


async def season_info(session: AsyncSession) -> SeasonInfo:
    season = await current_season(session)
    left = max(0, int((season.ends_at - datetime.now(timezone.utc)).total_seconds()))
    return SeasonInfo(season, await bp_repo.premium_count(session, season.id), left)


async def start_new_season(session: AsyncSession, admin_id: int) -> int:
    """Закрыть текущий сезон сейчас и открыть следующий. → номер нового сезона."""
    old = await current_season(session)
    await bp_repo.end_season(session, old.id, datetime.now(timezone.utc))
    new = await current_season(session)  # ends_at старого уже в прошлом → создаётся номер+1
    await audit.log(session, admin_id, AUDIT_SE_NEW_SEASON, None, {"old": old.number, "new": new.number})
    await session.commit()
    return new.number


async def pass_info(session: AsyncSession, user_id: int) -> PassInfo:
    season = await current_season(session)
    bp = await bp_repo.get(session, user_id, season.id)
    if bp is None:
        return PassInfo(season, 0, 0, False, 0, 0)
    return PassInfo(season, bp.xp, level_from_xp(bp.xp), bp.is_premium, bp.claimed_free, bp.claimed_premium)


async def give_xp(session: AsyncSession, admin_id: int, user_id: int, delta: int) -> int | None:
    """Прямая запись опыта пасса (без буста/квестов). → новый опыт; None — число вне диапазона."""
    if abs(delta) > XP_LIMIT:
        return None
    season = await current_season(session)
    bp = await bp_repo.lock(session, user_id, season.id)
    bp.xp = max(0, bp.xp + delta)
    await audit.log(session, admin_id, AUDIT_SE_XP, user_id, {"season": season.number, "delta": delta, "xp": bp.xp})
    await session.commit()
    return bp.xp


async def toggle_premium(session: AsyncSession, admin_id: int, user_id: int) -> bool:
    season = await current_season(session)
    bp = await bp_repo.lock(session, user_id, season.id)
    bp.is_premium = not bp.is_premium
    await audit.log(session, admin_id, AUDIT_SE_PREMIUM, user_id, {"season": season.number, "premium": bp.is_premium})
    await session.commit()
    return bp.is_premium


async def reset_claims(session: AsyncSession, admin_id: int, user_id: int) -> None:
    season = await current_season(session)
    bp = await bp_repo.lock(session, user_id, season.id)
    bp.claimed_free, bp.claimed_premium = 0, 0
    await session.execute(
        delete(BattlePassClaim).where(BattlePassClaim.user_id == user_id, BattlePassClaim.season_id == season.id)
    )
    await audit.log(session, admin_id, AUDIT_SE_RESET_CLAIMS, user_id, {"season": season.number})
    await session.commit()


async def quest_status(session: AsyncSession, user_id: int) -> QuestStatus:
    return await get_status(session, user_id)  # создаёт набор дня, если его ещё нет (коммитит)


async def complete_quest(session: AsyncSession, admin_id: int, user_id: int, slot: int) -> bool:
    """Засчитать остаток цели через обычное событие игры (`on_event`) — опыт пасса выдаётся как обычно."""
    quests = await quest_repo.list_day(session, user_id, today())
    quest = next((q for q in quests if q.slot == slot), None)
    if quest is None or quest.completed_at is not None:
        return False
    await on_event(session, user_id, quest.task, max(1, quest.target - quest.progress))
    await audit.log(session, admin_id, AUDIT_SE_QUEST_DONE, user_id, {"slot": slot, "task": quest.task, "code": quest.code})
    await session.commit()
    return True


async def reroll_set(session: AsyncSession, admin_id: int, user_id: int) -> None:
    """Удалить набор и состояние дня — при следующем заходе игрока (или просмотре) соберётся новый."""
    await session.execute(delete(DailyQuest).where(DailyQuest.user_id == user_id, DailyQuest.day == today()))
    await session.execute(delete(DailyQuestState).where(DailyQuestState.user_id == user_id))
    await audit.log(session, admin_id, AUDIT_SE_QUEST_REROLL, user_id, {})
    await session.commit()
