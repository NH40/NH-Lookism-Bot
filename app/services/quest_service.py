import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.daily_quest import DailyQuest
from app.constants.quests import (
    DAILY_QUESTS, QUESTS_BY_ID, ALL_DONE_QUEST,
    DAILY_QUESTS_COUNT, COOLDOWN_DAYS,
)


class QuestService:

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ─────────────────────────────────────────────────────────────────────────
    # Назначение и получение заданий дня
    # ─────────────────────────────────────────────────────────────────────────

    async def get_or_create_quests(
        self, session: AsyncSession, user: User
    ) -> list[DailyQuest]:
        today = self._today()

        # Уже созданы на сегодня?
        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
            ).order_by(DailyQuest.id)
        )
        existing = result.scalars().all()
        if existing:
            # Проверяем, что квесты в новом формате (все quest_id известны)
            if all(QUESTS_BY_ID.get(q.quest_id) is not None for q in existing):
                return existing
            # Старый формат — удаляем и создаём заново
            for q in existing:
                await session.delete(q)
            await session.flush()

        # ── Выбираем 9 заданий из пула с учётом КД ───────────────────────────
        selected_ids = await self._pick_daily_quests(session, user.id, today)

        # Создаём строки в БД
        for quest_id in selected_ids:
            session.add(DailyQuest(
                user_id=user.id,
                quest_id=quest_id,
                progress=0,
                date=today,
            ))

        # Специальное задание «Выполнить все 9»
        session.add(DailyQuest(
            user_id=user.id,
            quest_id="all_done",
            progress=0,
            date=today,
        ))

        await session.flush()

        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
            ).order_by(DailyQuest.id)
        )
        return result.scalars().all()

    async def _pick_daily_quests(
        self, session: AsyncSession, user_id: int, today: str
    ) -> list[str]:
        """Выбирает DAILY_QUESTS_COUNT заданий с учётом окна КД."""
        # Получаем задания, назначенные за последние COOLDOWN_DAYS дней
        window_start = (
            datetime.strptime(today, "%Y-%m-%d") - timedelta(days=COOLDOWN_DAYS)
        ).strftime("%Y-%m-%d")

        recent_result = await session.execute(
            select(DailyQuest.quest_id).where(
                DailyQuest.user_id == user_id,
                DailyQuest.quest_id != "all_done",
                DailyQuest.date > window_start,
                DailyQuest.date < today,       # только прошлые дни
            )
        )
        recently_used: set[str] = set(recent_result.scalars().all())

        all_ids = [q.quest_id for q in DAILY_QUESTS]
        available = [qid for qid in all_ids if qid not in recently_used]

        # Если доступных меньше нужного — берём часть из «тёплого» резерва
        if len(available) < DAILY_QUESTS_COUNT:
            # Самые старые использованные
            older_result = await session.execute(
                select(DailyQuest.quest_id).where(
                    DailyQuest.user_id == user_id,
                    DailyQuest.quest_id != "all_done",
                    DailyQuest.date <= window_start,
                ).order_by(DailyQuest.date.asc())
            )
            older = [qid for qid in older_result.scalars().all() if qid not in available]
            available = available + older

        # Если всё равно мало — берём из полного пула
        if len(available) < DAILY_QUESTS_COUNT:
            available = all_ids[:]

        return random.sample(available, min(DAILY_QUESTS_COUNT, len(available)))

    # ─────────────────────────────────────────────────────────────────────────
    # Отслеживание прогресса
    # ─────────────────────────────────────────────────────────────────────────

    async def add_progress(
        self, session: AsyncSession, user: User,
        progress_key: str, amount: int = 1
    ) -> None:
        """
        Обновляет прогресс всех активных заданий дня, у которых
        progress_key совпадает с переданным ключом.

        Вызывается из хендлеров/планировщиков с ключами:
        attacks, wins, recruit, train, income,
        raid_start, raid_win, gacha_pull, card_duel, card_fusion,
        market_sell, market_buy
        """
        today = self._today()

        # Убеждаемся, что квесты на сегодня созданы (и в новом формате)
        await self.get_or_create_quests(session, user)

        # Загружаем сегодняшние задания пользователя
        result = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
                DailyQuest.quest_id != "all_done",
                DailyQuest.is_completed == False,
            )
        )
        quests = result.scalars().all()

        completed_new = False
        for quest in quests:
            cfg = QUESTS_BY_ID.get(quest.quest_id)
            if not cfg:
                continue
            # Проверяем совпадение ключа (progress_key или quest_id для старых)
            pkey = cfg.progress_key if cfg.progress_key else cfg.quest_id
            if pkey != progress_key:
                continue
            quest.progress = min(quest.progress + amount, cfg.target)
            if quest.progress >= cfg.target:
                quest.is_completed = True
                completed_new = True

        if completed_new:
            await self._update_all_done(session, user, today)

        await session.flush()

    async def _update_all_done(
        self, session: AsyncSession, user: User, today: str
    ) -> None:
        # Считаем сколько обычных заданий выполнено сегодня
        completed_count_result = await session.execute(
            select(func.count(DailyQuest.id)).where(
                DailyQuest.user_id == user.id,
                DailyQuest.date == today,
                DailyQuest.quest_id != "all_done",
                DailyQuest.is_completed == True,
            )
        )
        completed_count = completed_count_result.scalar() or 0

        all_done_r = await session.execute(
            select(DailyQuest).where(
                DailyQuest.user_id == user.id,
                DailyQuest.quest_id == "all_done",
                DailyQuest.date == today,
            )
        )
        all_done = all_done_r.scalar_one_or_none()
        if not all_done:
            return  # задание ещё не создано (пользователь не открывал квесты)

        cfg = QUESTS_BY_ID.get("all_done")
        if cfg:
            all_done.progress = min(completed_count, cfg.target)
            if all_done.progress >= cfg.target:
                all_done.is_completed = True

        await session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # Получение награды
    # ─────────────────────────────────────────────────────────────────────────

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
            user.tickets += cfg.reward_tickets
        user.daily_quests_completed = (user.daily_quests_completed or 0) + 1

        await session.flush()

        return {
            "ok": True,
            "coins": cfg.reward_coins,
            "tickets": cfg.reward_tickets,
        }


quest_service = QuestService()
