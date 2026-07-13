"""
horse_shop_tick — спавн/закрытие ивент-магазина «Лавка коня».
Тикает раз в минуту.
"""
import logging
import random
from datetime import datetime, timezone, timedelta

from app.database import AsyncSessionFactory
from app.config.game_balance import (
    HORSE_SHOP_MIN_INTERVAL_HOURS,
    HORSE_SHOP_MAX_INTERVAL_HOURS,
    HORSE_SHOP_DURATION_HOURS,
)

logger = logging.getLogger(__name__)


async def horse_shop_tick() -> None:
    from app.repositories.horse_shop_repo import horse_shop_repo

    async with AsyncSessionFactory() as session:
        async with session.begin():
            # ── Шаг 1: закрыть истёкшее событие ───────────────────────────────
            expired = await horse_shop_repo.get_expired_active(session)
            if expired:
                next_spawn = datetime.now(timezone.utc) + timedelta(
                    hours=random.uniform(HORSE_SHOP_MIN_INTERVAL_HOURS, HORSE_SHOP_MAX_INTERVAL_HOURS)
                )
                await horse_shop_repo.finish_event(session, expired, next_spawn_at=next_spawn)
                logger.info(f"horse_shop_tick: закрыта лавка id={expired.id}, следующая через {next_spawn}")
                return  # не спавним в том же тике

            # ── Шаг 2: проверка спавна ─────────────────────────────────────────
            current = await horse_shop_repo.get_current_event(session)
            if current:
                return

            pending = await horse_shop_repo.get_pending_spawn(session)
            if pending is None:
                last = await horse_shop_repo.get_last_event(session)
                if last is not None:
                    return  # next_spawn_at ещё в будущем
                # Первый запуск — планируем первый спавн, не создаём сразу
                first_spawn = datetime.now(timezone.utc) + timedelta(
                    hours=random.uniform(HORSE_SHOP_MIN_INTERVAL_HOURS, HORSE_SHOP_MAX_INTERVAL_HOURS)
                )
                from app.models.horse_shop import HorseShopEvent
                placeholder = HorseShopEvent(
                    status="expired",
                    started_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc),
                    next_spawn_at=first_spawn,
                )
                session.add(placeholder)
                await session.flush()
                logger.info(f"horse_shop_tick: первый спавн запланирован на {first_spawn}")
                return

            now = datetime.now(timezone.utc)
            event = await horse_shop_repo.create_event(
                session, started_at=now, expires_at=now + timedelta(hours=HORSE_SHOP_DURATION_HOURS),
            )
            logger.info(f"horse_shop_tick: открыта лавка коня id={event.id}")

    await _notify_horse_shop_spawn()


async def _notify_horse_shop_spawn() -> None:
    try:
        from app.bot_instance import get_bot
        from app.database import AsyncSessionFactory
        from app.models.user import User
        from sqlalchemy import select

        bot = get_bot()
        if not bot:
            return

        text = (
            "🐴 <b>Лавка коня открылась!</b>\n\n"
            "В честь великого торговца первого поколения была создана "
            "специальная лавка — загляни, пока не закрылась!\n\n"
            f"⏳ Открыта на <b>{HORSE_SHOP_DURATION_HOURS} часа</b>.\n"
            "Открой 💰 Экономика → 🐴 Лавка коня!"
        )

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(User.tg_id).where(
                    User.notifications_enabled == True,
                    User.notif_horse_shop == True,
                )
            )
            tg_ids = list(result.scalars().all())

        import pathlib
        image_path = pathlib.Path("images/shop/Kon.png")

        import asyncio
        from app.scheduler.tasks.notifications import _NOTIF_SEM

        async def _send_one(tg_id: int) -> None:
            async with _NOTIF_SEM:
                try:
                    if image_path.exists():
                        from aiogram.types import FSInputFile
                        await bot.send_photo(
                            tg_id, FSInputFile(str(image_path)), caption=text, parse_mode="HTML",
                        )
                    else:
                        await bot.send_message(tg_id, text, parse_mode="HTML")
                except Exception:
                    pass

        await asyncio.gather(*[_send_one(tid) for tid in tg_ids])
        logger.info(f"horse_shop_tick: уведомление о лавке отправлено {len(tg_ids)} игрокам")
    except Exception as exc:
        logger.warning(f"_notify_horse_shop_spawn error: {exc}")
