"""
Планировщик: спавн боссов и завершение истёкших.
Тикает каждую минуту.
"""
import logging
from datetime import datetime, timezone

from app.database import AsyncSessionFactory
from app.constants.bosses import BOSS_SPAWN_HOURS

logger = logging.getLogger(__name__)


async def boss_tick() -> None:
    """
    1. Если есть активный истёкший босс — завершаем и раздаём награды.
    2. Если нет активного босса и время спавна пришло — спавним нового.
    """
    from app.repositories.boss_repo import boss_repo
    from app.services.boss_service import boss_service

    async with AsyncSessionFactory() as session:
        async with session.begin():
            # ── Шаг 1: завершение истёкшего босса ────────────────────────────
            expired = await boss_repo.get_expired_active(session)
            if expired:
                logger.info(f"boss_tick: завершаем boss_id={expired.boss_id} id={expired.id}")
                try:
                    result = await boss_service.finalize_boss(session, expired)
                    await _notify_boss_result(result)
                except Exception as exc:
                    logger.error(f"boss_tick: ошибка завершения id={expired.id}: {exc}", exc_info=True)
                return  # не спавним в том же тике

            # ── Шаг 2: проверка спавна ────────────────────────────────────────
            # Если нет активного босса — проверяем, пора ли спавнить
            current = await boss_repo.get_current_boss(session)
            if current:
                return  # уже есть активный босс

            pending = await boss_repo.get_pending_spawn(session)
            if pending is None:
                # Никогда не было боссов или next_spawn_at ещё не пришёл
                last = await boss_repo.get_last_boss(session)
                if last is not None:
                    # next_spawn_at ещё в будущем
                    return
                # Первый запуск — спавним сразу
                logger.info("boss_tick: первый спавн босса")
            else:
                logger.info(f"boss_tick: спавним следующего босса (прошлый boss_id={pending.boss_id})")

            try:
                boss = await boss_service.spawn_boss(session)
                await _notify_boss_spawn(boss)
            except Exception as exc:
                logger.error(f"boss_tick: ошибка спавна: {exc}", exc_info=True)


# ── Уведомления ───────────────────────────────────────────────────────────────

async def _notify_boss_spawn(boss) -> None:
    """Уведомляет всех игроков с включёнными нотификациями о появлении босса."""
    try:
        from app.bot_instance import get_bot
        from app.scheduler.tasks.notifications import _send_notifications
        from app.database import AsyncSessionFactory
        from app.models.user import User
        from app.constants.bosses import BOSS_MAP, BOSS_DURATION_HOURS
        from sqlalchemy import select

        bot = get_bot()
        if not bot:
            return

        cfg = BOSS_MAP.get(boss.boss_id)
        if not cfg:
            return

        from app.services.boss_service import fmt_hp as fhp
        text = (
            f"⚔️ <b>Появился новый босс!</b>\n\n"
            f"{cfg.emoji} <b>{cfg.name}</b>\n"
            f"❤️ HP: <b>{fhp(boss.base_max_hp)}</b>\n\n"
            f"{cfg.special_desc}\n\n"
            f"⏳ На победу: <b>{BOSS_DURATION_HOURS} часа</b>\n"
            f"Открой <b>Боссы</b> → <b>Атаковать</b>!"
        )

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(User.tg_id).where(
                    User.notifications_enabled == True,
                    User.notif_boss == True,
                )
            )
            tg_ids = list(result.scalars().all())

        await _send_notifications(bot, tg_ids, text)
        logger.info(f"boss_tick: уведомление о спавне отправлено {len(tg_ids)} игрокам")
    except Exception as exc:
        logger.warning(f"_notify_boss_spawn error: {exc}")


async def _notify_boss_result(result: dict) -> None:
    """Уведомляет всех участников + всех игроков о финале босса."""
    try:
        from app.bot_instance import get_bot
        from app.scheduler.tasks.notifications import _send_notifications
        from app.database import AsyncSessionFactory
        from app.models.user import User
        from sqlalchemy import select

        bot = get_bot()
        if not bot:
            return

        emoji = result["boss_emoji"]
        name = result["boss_name"]
        defeated = result["defeated"]
        outcome_phrase = result.get("outcome_phrase")

        if defeated:
            outcome_icon = "🏆"
            outcome_text = "ПОБЕДА! Босс повержен!"
        else:
            outcome_icon = "💀"
            outcome_text = "ПОРАЖЕНИЕ. Босс не сломлен."

        phrase_line = f"\n<i>«{outcome_phrase}»</i>" if outcome_phrase else ""

        # Уведомление для всех участников
        rewards_map: dict[int, dict] = {r["user_id"]: r for r in result["rewards"]}

        async with AsyncSessionFactory() as session:
            if rewards_map:
                from app.models.user import User as UserModel
                users_result = await session.execute(
                    select(UserModel).where(UserModel.id.in_(list(rewards_map.keys())))
                )
                users = list(users_result.scalars().all())
                for u in users:
                    if not u.notifications_enabled:
                        continue
                    r = rewards_map.get(u.id, {})
                    tickets = r.get("tickets", 0)
                    damage = r.get("damage", 0)
                    place = r.get("place")
                    coins_delta = r.get("coins_delta", 0)

                    from app.services.boss_service import fmt_hp as fhp, fmt_boss_coins as fcoins
                    place_str = f"🥇🥈🥉4️⃣5️⃣"[place - 1] if place and place <= 5 else "👥"

                    personal_text = (
                        f"{outcome_icon} <b>{emoji} {name} — {outcome_text}</b>"
                        f"{phrase_line}\n\n"
                        f"{place_str} Твоё место: <b>{'Топ ' + str(place) if place else 'Участник'}</b>\n"
                        f"⚔️ Нанесено урона: <b>{fhp(damage)}</b>\n"
                        f"🎟 Получено тикетов: <b>+{tickets}</b>"
                    )
                    if coins_delta:
                        sign = "+" if coins_delta > 0 else ""
                        personal_text += f"\n💰 Монеты: <b>{sign}{fcoins(abs(coins_delta))}</b>"
                    try:
                        await bot.send_message(u.tg_id, personal_text, parse_mode="HTML")
                    except Exception:
                        pass

            # Глобальное уведомление (всем с нотификациями о боссах)
            next_spawn_at = result.get("next_spawn_at")
            if next_spawn_at:
                from datetime import datetime as _dt, timezone as _tz
                secs_to_next = max(0, int((next_spawn_at - _dt.now(_tz.utc)).total_seconds()))
                hours, rem = divmod(secs_to_next, 3600)
                mins = rem // 60
                next_spawn_str = f"{hours} ч {mins} мин" if hours else f"{mins} мин"
            else:
                next_spawn_str = f"{BOSS_SPAWN_HOURS} ч"
            global_text = (
                f"{outcome_icon} <b>{emoji} {name} — {outcome_text}</b>"
                f"{phrase_line}\n\n"
                f"👥 Участников: <b>{result['participant_count']}</b>\n"
                f"⏰ Следующий босс появится через <b>{next_spawn_str}</b>"
            )
            all_result = await session.execute(
                select(User.tg_id).where(
                    User.notifications_enabled == True,
                    User.notif_boss == True,
                )
            )
            all_tg_ids = list(all_result.scalars().all())

        await _send_notifications(bot, all_tg_ids, global_text)
        logger.info(f"boss_tick: уведомление о финале отправлено {len(all_tg_ids)} игрокам")
    except Exception as exc:
        logger.warning(f"_notify_boss_result error: {exc}", exc_info=True)
