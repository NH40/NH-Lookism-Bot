import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.potion_service import potion_service
from app.repositories.user_repo import user_repo


async def get_effective_power(session: AsyncSession, user: User) -> int:
    """Боевая мощь с учётом зелья силы и крит-шанса легенды."""
    base = await potion_service.get_effective_power(session, user)
    return base


async def roll_crit(session: AsyncSession, user: User) -> tuple[int, bool]:
    """
    Возвращает (effective_power, is_crit).
    Крит: ×3 если есть титул legend_gen1 и random() < 0.02
    """
    from app.repositories.title_repo import title_repo
    power = await get_effective_power(session, user)
    has_legend = await title_repo.has_title(session, user.id, "legend_gen1")
    if has_legend and random.random() < 0.02:
        return power * 3, True
    return power, False


async def fight_district(
    session: AsyncSession,
    user: User,
    district_power: int,
) -> dict:
    """
    Бой с районом (бот).
    Возвращает {"win": bool, "is_crit": bool, "user_power": int, "district_power": int}
    """
    from app.models.skill import UserMastery
    from sqlalchemy import select

    user_power, is_crit = await roll_crit(session, user)

    # Бонус выносливости — можно побеждать врагов сильнее на X%
    mastery_result = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = mastery_result.scalar_one_or_none()
    endurance_bonus = 0
    if mastery:
        endurance_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        endurance_bonus = endurance_levels.get(mastery.endurance, 0)

    effective_threshold = int(district_power * (1 - endurance_bonus / 100))
    win = user_power >= effective_threshold

    return {
        "win": win,
        "is_crit": is_crit,
        "user_power": user_power,
        "district_power": district_power,
        "effective_threshold": effective_threshold,
    }


async def fight_player(
    session: AsyncSession,
    attacker: User,
    defender: User,
) -> dict:
    """
    PvP бой между двумя игроками.
    Возвращает {"win": bool, "is_crit": bool, "attacker_power": int, "defender_power": int}
    """
    attacker_power, is_crit = await roll_crit(session, attacker)
    defender_power = await get_effective_power(session, defender)

    # Защита = 70% от реальной мощи защитника
    effective_defense = int(defender_power * 0.7)

    # Великий: влияние не падает ниже 100
    win = attacker_power >= effective_defense

    return {
        "win": win,
        "is_crit": is_crit,
        "attacker_power": attacker_power,
        "defender_power": defender_power,
        "effective_defense": effective_defense,
    }