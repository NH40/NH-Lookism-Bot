"""
Ежедневные бонусы от круговых донатов.

circ_daily_districts (Архангел круг 10):
  Для игроков в фазе Кулак — выдаётся реальный fist-город с N районами.
  Для остальных фаз — начисляется NHCoin-эквивалент (N × DISTRICT_DAILY_COIN_RATE).
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User

logger = logging.getLogger(__name__)

# Монетный эквивалент одного района для не-фист фаз
DISTRICT_DAILY_COIN_RATE = 500


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

                    if user.phase == "fist":
                        # Выдаём реальный fist-город с districts районами
                        from app.services.game_service import game_service
                        from app.services.business_service import business_service
                        from app.models.city import City, District
                        from sqlalchemy import func

                        await game_service._give_fist_city_one(session, user, districts)

                        # Пересчитываем количество fist-городов и доход
                        fist_cnt = await session.scalar(
                            select(func.count(func.distinct(District.city_id)))
                            .join(City, City.id == District.city_id)
                            .where(
                                District.owner_id == user.id,
                                District.is_captured == True,
                                City.phase == "fist",
                            )
                        ) or 0
                        user.fist_cities_count = fist_cnt
                        await business_service._recalc_income(session, user)

                        user.circ_daily_districts_at = datetime.now(timezone.utc)
                        notifications.append((
                            user.tg_id,
                            f"🏙 <b>Архангел подарил вам город!</b>\n\n"
                            f"Ежедневный бонус: +<b>{districts}</b> районов.\n"
                            f"Городов Кулака: <b>{fist_cnt}/10</b>",
                        ))
                        count += 1
                    else:
                        # Не Кулак — монетный эквивалент
                        bonus = districts * DISTRICT_DAILY_COIN_RATE
                        user.nh_coins += bonus
                        user.circ_daily_districts_at = datetime.now(timezone.utc)
                        from app.utils.formatters import fmt_num
                        notifications.append((
                            user.tg_id,
                            f"👼 <b>Ежедневный бонус Архангела</b>\n\n"
                            f"+{fmt_num(bonus)} NHCoin "
                            f"({districts} районов × {DISTRICT_DAILY_COIN_RATE})\n"
                            f"<i>В фазе Кулака вместо монет выдаётся реальный город.</i>",
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
