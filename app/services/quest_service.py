from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.daily_quest import DailyQuest
from app.constants.quests import DAILY_QUESTS, QUESTS_BY_ID, QuestConfig


class QuestService:

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def get_or_create_quests(
        self, session: AsyncSession, user: User
    ) -> list[DailyQuest]:
        today = self._today()

        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
            )
        )
        quests = result.scalars().all()

        existing_ids = {q.quest_id for q in quests}
        for cfg in DAILY_QUESTS:
            if cfg.quest_id not in existing_ids:
                quest = DailyQuest(
                    user_id=user.id,
                    quest_id=cfg.quest_id,
                    progress=0,
                    date=today,
                )
                session.add(quest)

        await session.flush()

        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
            ).order_by(DailyQuest.id)
        )
        return result.scalars().all()

    async def add_progress(
        self, session: AsyncSession, user: User,
        quest_id: str, amount: int = 1
    ) -> None:
        today = self._today()
        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.quest_id == quest_id,
                DailyQuest.date == today,
            )
        )
        quest = result.scalar_one_or_none()
        if not quest:
            quest = DailyQuest(
                user_id=user.id,
                quest_id=quest_id,
                progress=0,
                date=today,
            )
            session.add(quest)
            await session.flush()

        if quest.is_completed:
            return

        cfg = QUESTS_BY_ID.get(quest_id)
        if not cfg:
            return

        quest.progress = min(quest.progress + amount, cfg.target)
        if quest.progress >= cfg.target:
            quest.is_completed = True

            # Обновляем прогресс all_done
            if quest_id != "all_done":
                await self._update_all_done(session, user, today)

        await session.flush()

    async def _update_all_done(
        self, session: AsyncSession, user: User, today: str
    ) -> None:
        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
                DailyQuest.quest_id != "all_done",
                DailyQuest.is_completed == True,
            )
        )
        completed_count = len(result.scalars().all())

        all_done_r = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.quest_id == "all_done",
                DailyQuest.date == today,
            )
        )
        all_done = all_done_r.scalar_one_or_none()
        if not all_done:
            all_done = DailyQuest(
                user_id=user.id,
                quest_id="all_done",
                progress=0,
                date=today,
            )
            session.add(all_done)
            await session.flush()

        cfg = QUESTS_BY_ID.get("all_done")
        if cfg:
            all_done.progress = min(completed_count, cfg.target)
            if all_done.progress >= cfg.target:
                all_done.is_completed = True

        await session.flush()

    async def claim_reward(
        self, session: AsyncSession, user: User, quest_id: str
    ) -> dict:
        today = self._today()
        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.quest_id == quest_id,
                DailyQuest.date == today,
            )
        )
        quest = result.scalar_one_or_none()

        if not quest:
            return {"ok": False, "reason": "Задание не найдено"}
        if not quest.is_completed:
            return {"ok": False, "reason": "Задание не выполнено"}
        if quest.is_claimed:
            return {"ok": False, "reason": "Награда уже получена"}

        cfg = QUESTS_BY_ID.get(quest_id)
        if not cfg:
            return {"ok": False, "reason": "Конфиг не найден"}

        quest.is_claimed = True
        user.nh_coins += cfg.reward_coins
        if cfg.reward_tickets > 0:
            user.tickets = min(user.tickets + cfg.reward_tickets, user.max_tickets)

        await session.flush()

        return {
            "ok": True,
            "coins": cfg.reward_coins,
            "tickets": cfg.reward_tickets,
        }


quest_service = QuestService()