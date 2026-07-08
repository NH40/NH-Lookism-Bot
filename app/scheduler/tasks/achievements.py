"""
Планировщик: проверка новых достижений для недавно активных игроков.
Тикает раз в ACHIEVEMENT_TICK_SECONDS, не сканирует всю таблицу пользователей —
только тех, кто менял свои данные (updated_at) за последнее окно.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models.user import User
from app.utils.formatters import fmt_num

logger = logging.getLogger(__name__)

ACTIVE_WINDOW_MINUTES = 20


async def achievement_tick() -> None:
    from app.services.title_service import title_service

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    to_notify: list[tuple[int, list[dict]]] = []

    async with AsyncSessionFactory() as session:
        async with session.begin():
            users_r = await session.execute(
                select(User).where(
                    User.updated_at >= cutoff,
                    User.notifications_enabled == True,
                    User.notif_achievements == True,
                )
            )
            users = users_r.scalars().all()

            for user in users:
                try:
                    async with session.begin_nested():
                        granted = await title_service.check_achievements(session, user)
                        if granted:
                            to_notify.append((user.tg_id, granted))
                except Exception as exc:
                    logger.error(f"achievement_tick: user_id={user.id} error: {exc}")
        # ← транзакция закрыта; соединение с БД освобождено

    if not to_notify:
        return

    from app.bot_instance import get_bot
    bot = get_bot()
    if not bot:
        return

    for tg_id, granted in to_notify:
        lines = ["🎉 <b>Новые достижения!</b>\n"]
        total_coins = 0
        for g in granted:
            lines.append(f"✅ {g['name']}\n  └ {g['bonus_description']}")
            total_coins += g.get("coins", 0)
        if total_coins:
            lines.append(f"\n💰 Итого монет: +{fmt_num(total_coins)}")
        try:
            await bot.send_message(tg_id, "\n".join(lines), parse_mode="HTML")
        except Exception as exc:
            logger.warning(f"achievement_tick notify failed tg_id={tg_id}: {exc}")
