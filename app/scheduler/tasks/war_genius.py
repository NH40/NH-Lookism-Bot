"""
war_genius_tick — авто-атака рейдов для пользователей с навыком «Гений войны».
Тикает каждую минуту, независимо от Ультра Инстинкта.

Логика:
  - Пользователь сам запускает рейд на нужного босса.
  - Если у него активный рейд и КД атаки прошёл — бот атакует автоматически.
  - Уровень Гения войны определяет, на каких боссов работает авто-атака.
"""
import logging
from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.raid import RaidSession
from app.constants.training import WAR_GENIUS_BOSS_MAP

logger = logging.getLogger(__name__)


async def war_genius_tick() -> None:
    async with AsyncSessionFactory() as session:
        # Берём id пользователей с активным Гением войны
        user_ids = list((await session.execute(
            select(User.id).where(User.war_genius_level > 0)
        )).scalars())

    if not user_ids:
        return

    async with AsyncSessionFactory() as session:
        async with session.begin():
            for user_id in user_ids:
                try:
                    async with session.begin_nested():
                        await _auto_attack_for_user(session, user_id)
                except Exception as exc:
                    logger.error(f"war_genius_tick: user_id={user_id} error: {exc}")


async def _auto_attack_for_user(session, user_id: int) -> None:
    from app.services.cooldown_service import cooldown_service
    from app.services.raid_service import raid_service

    user = await session.get(User, user_id)
    if not user:
        return

    war_genius = getattr(user, "war_genius_level", 0)
    if war_genius == 0:
        return

    # Доступные боссы для данного уровня Гения войны (все до текущего уровня включительно)
    allowed_pairs = set()
    for lvl in range(1, war_genius + 1):
        pair = WAR_GENIUS_BOSS_MAP.get(lvl)
        if pair:
            allowed_pairs.add(pair)

    # Ищем активный рейд пользователя на одного из разрешённых боссов
    result = await session.execute(
        select(RaidSession).where(
            RaidSession.user_id == user_id,
            RaidSession.is_finished == False,
        )
    )
    raid = result.scalar_one_or_none()
    if not raid:
        return

    if (raid.clan_id, raid.boss_id) not in allowed_pairs:
        return  # Рейд на босса, не покрытого текущим уровнем

    # Проверяем КД атаки
    attack_cd_key = raid_service.attack_cd_key(raid.id, user_id)
    ttl = await cooldown_service.get_ttl(attack_cd_key)
    if ttl > 0:
        return  # КД ещё не прошёл

    # Атакуем
    result_dict = await raid_service.attack_boss(session, user, raid.id)
    if result_dict.get("ok"):
        if result_dict.get("boss_killed"):
            logger.info(
                f"war_genius_tick: user={user_id} auto-killed boss {raid.boss_id} "
                f"fragments={result_dict.get('fragments', 0)}"
            )
        else:
            logger.debug(
                f"war_genius_tick: user={user_id} auto-attacked {raid.boss_id} "
                f"dmg={result_dict.get('damage', 0)}"
            )
