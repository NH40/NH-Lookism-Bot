"""
Ежедневные бонусы от круговых донатов.

circ_daily_districts (Архангел круг 10):
  Начисляет N бонусных районов (через business_service.add_bonus_districts —
  личный "business"-квартал вне карты, засчитывается в доход как обычные
  захваченные районы). До патча 1.3.1 (Кулак ещё был в прогрессии) выдавался
  настоящий fist-город; фаза Кулака убрана из прогрессии — теперь всем одинаково.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.models.user import User

logger = logging.getLogger(__name__)

# Монетный эквивалент одного района для не-фист фаз
DISTRICT_DAILY_COIN_RATE = 50_000


async def daily_tick():
    """
    Ежедневный тик — начисляет бонус circ_daily_districts (Архангел круг 10).
    Запускается один раз в сутки (в 00:00 UTC).
    """
    notifications: list[tuple[int, str]] = []  # (tg_id, text)

    async with AsyncSessionFactory() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.circ_daily_districts > 0)
            )
            users = result.scalars().all()
            count = 0

            for user in users:
                try:
                    districts = getattr(user, "circ_daily_districts", 0)
                    if districts <= 0:
                        continue

                    # Добавляем бонусные районы (создаёт District-строки в бонус-городе
                    # и пересчитывает доход/налог — bonus_business_districts сам
                    # по себе не создаёт районов и не влияет на income_per_minute)
                    from app.services.business_service import business_service
                    await business_service.add_bonus_districts(session, user, districts)
                    user.bonus_business_districts = getattr(user, "bonus_business_districts", 0) + districts

                    user.circ_daily_districts_at = datetime.now(timezone.utc)
                    
                    # Сбрасываем daily_districts (они уже начислены)
                    # Но не сбрасываем полностью, т.к. они могут быть от нескольких десятков
                    # Оставляем как есть, т.к. _apply_one_donat их пересчитает при rebuild
                    
                    notifications.append((
                        user.tg_id,
                        f"🏙 <b>Архангел подарил вам районы!</b>\n\n"
                        f"Ежедневный бонус: +<b>{districts}</b> районов.\n"
                        f"Всего бонусных районов: <b>{user.bonus_business_districts}</b>",
                    ))
                    count += 1

                except Exception as e:
                    logger.error(f"daily_tick error for user {user.id}: {e}", exc_info=True)

            if count:
                logger.info(f"daily_tick: обработано {count} пользователей с circ_daily_districts")

    # Отправляем уведомления ПОСЛЕ коммита
    if not notifications:
        return

    bot_instance = None
    try:
        from app.bot_instance import get_bot
        bot_instance = get_bot()
    except Exception:
        pass

    if not bot_instance:
        return

    for tg_id, text in notifications:
        try:
            await bot_instance.send_message(tg_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"daily_tick notif error tg_id={tg_id}: {e}")