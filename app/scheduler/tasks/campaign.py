"""
Планировщик: завершение истёкших походов.
Тикает каждые 2 минуты, ищет кампании с ends_at <= now и обрабатывает их.
"""
import logging

from app.database import AsyncSessionFactory

logger = logging.getLogger(__name__)


async def campaign_tick() -> None:
    """Завершает все истёкшие активные походы и уведомляет игроков."""
    from app.repositories.campaign_repo import campaign_repo
    from app.services.campaign_service import campaign_service
    from app.models.user import User
    from sqlalchemy import select

    to_notify: list[tuple[int, object, dict]] = []

    async with AsyncSessionFactory() as session:
        async with session.begin():
            expired = await campaign_repo.get_expired_active(session)
            if not expired:
                return

            logger.info(f"campaign_tick: обрабатываем {len(expired)} походов")

            user_ids = {camp.user_id for camp in expired}
            users_r = await session.execute(
                select(User.id, User.tg_id, User.notifications_enabled).where(
                    User.id.in_(user_ids)
                )
            )
            users_map = {row.id: (row.tg_id, row.notifications_enabled) for row in users_r.all()}

            for camp in expired:
                try:
                    result = await campaign_service.process_expired(session, camp)
                    info = users_map.get(camp.user_id)
                    if info and info[1]:
                        to_notify.append((info[0], camp, result))
                except Exception as exc:
                    logger.error(f"campaign_tick error camp_id={camp.id}: {exc}")
        # ← транзакция закрыта; соединение с БД освобождено

    # Отправляем уведомления ПОСЛЕ коммита
    for tg_id, camp, result in to_notify:
        await _notify_player(tg_id, camp, result)


async def _notify_player(tg_id: int, camp, result: dict) -> None:
    """Отправляет уведомление игроку о завершении похода."""
    try:
        from app.bot_instance import get_bot
        from app.constants.campaigns import CAMPAIGN_RANK_MAP, CAMPAIGN_RESOURCE_MAP

        bot = get_bot()
        if not bot:
            return

        rank_cfg = CAMPAIGN_RANK_MAP.get(camp.rank)
        res_cfg = CAMPAIGN_RESOURCE_MAP.get(camp.resource_type)

        rank_label = f"{rank_cfg.emoji} Ранг {camp.rank}" if rank_cfg else f"Ранг {camp.rank}"
        res_emoji = res_cfg.emoji if res_cfg else "📦"
        res_label = res_cfg.label if res_cfg else camp.resource_type

        if result["success"]:
            outcome = "✅ Успех!"
            res_line = f"\n{res_emoji} Добыто: <b>{result['resource_gained']:,} {res_label}</b>"
        else:
            outcome = "❌ Провал"
            res_line = ""

        text = (
            f"🗺 <b>Поход завершён — {outcome}</b>\n\n"
            f"{rank_label} | ⏱ {camp.duration_hours}ч"
            f"{res_line}\n\n"
            f"👥 Вернулось: <b>{result['statists_returned']}/{camp.statist_count}</b>\n"
            f"💀 Погибло: <b>{result['statists_lost']}</b>\n\n"
            f"Открой <b>Походы</b>, чтобы забрать результат!"
        )

        await bot.send_message(tg_id, text, parse_mode="HTML")
    except Exception as exc:
        logger.warning(f"campaign notify failed tg_id={tg_id}: {exc}")
