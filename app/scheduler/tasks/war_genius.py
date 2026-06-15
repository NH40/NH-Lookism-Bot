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
        from sqlalchemy import or_
        user_ids = list((await session.execute(
            select(User.id).where(
                or_(User.war_genius_level > 0, User.region_war_genius > 0)
            )
        )).scalars())

    if not user_ids:
        return

    async with AsyncSessionFactory() as session:
        async with session.begin():
            # Батч-загрузка всех юзеров одним запросом вместо N session.get()
            users_result = await session.execute(
                select(User).where(User.id.in_(user_ids))
            )
            users_map = {u.id: u for u in users_result.scalars().all()}

            for user_id in user_ids:
                try:
                    async with session.begin_nested():
                        await _auto_attack_for_user(session, user_id, users_map.get(user_id))
                except Exception as exc:
                    logger.error(f"war_genius_tick: user_id={user_id} error: {exc}")


async def _auto_attack_for_user(session, user_id: int, user=None) -> None:
    from app.services.cooldown_service import cooldown_service
    from app.services.raid_service import raid_service

    if user is None:
        user = await session.get(User, user_id)
    if not user:
        return

    # region_war_genius стакается с навыком (Ульсан даёт +N уровней, Сеул даёт MAX 5)
    war_genius = min(5, getattr(user, "war_genius_level", 0) + getattr(user, "region_war_genius", 0))
    if war_genius == 0:
        return

    allowed_pairs = set()
    for lvl in range(1, war_genius + 1):
        pair = WAR_GENIUS_BOSS_MAP.get(lvl)
        if pair:
            allowed_pairs.add(pair)

    # Ищем активный рейд пользователя — берём первый (scalar_one_or_none упадёт при дубликатах в БД)
    result = await session.execute(
        select(RaidSession).where(
            RaidSession.user_id == user_id,
            RaidSession.is_finished == False,
        )
    )
    raid = result.scalars().first()
    if not raid:
        return

    # Проверяем, что этот босс покрыт текущим уровнем Гения войны
    if (raid.clan_id, raid.boss_id) not in allowed_pairs:
        return

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
            logger.info(
                f"war_genius_tick: user={user_id} auto-attacked {raid.boss_id} "
                f"dmg={result_dict.get('damage', 0)}"
            )
    else:
        logger.warning(
            f"war_genius_tick: user={user_id} attack failed: {result_dict.get('reason')}"
        )
