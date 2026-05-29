import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.potion_service import potion_service
from app.repositories.user_repo import user_repo

# Shadow path: «Первый удар» — первая атака в бою дает +20% к мощи
_SHADOW_FIRST_ATTACK_BONUS = 0.20


async def get_effective_power(session: AsyncSession, user: User) -> int:
    """Боевая мощь с учётом зелья силы и крит-шанса легенды."""
    base = await potion_service.get_effective_power(session, user)
    return base


async def roll_crit(session: AsyncSession, user: User) -> tuple[int, bool]:
    """
    Возвращает (effective_power, is_crit).
    Крит: ×3 если есть титул legend_1gen и random() < 0.02 (2.4% с полным сетом genius_maker).
    """
    from app.repositories.title_repo import title_repo
    from app.data.titles import DONAT_TITLES
    power = await get_effective_power(session, user)
    has_legend = await title_repo.has_title(session, user.id, "legend_1gen")
    if has_legend:
        genius_set_titles = [t.title_id for t in DONAT_TITLES if t.set_id == "genius_maker"]
        owned = set(await title_repo.get_user_titles(session, user.id))
        crit_chance = 0.024 if all(tid in owned for tid in genius_set_titles) else 0.02
        if random.random() < crit_chance:
            return power * 3, True
    return power, False


def _apply_shadow_first_attack(user: User, power: int) -> tuple[int, bool]:
    """
    Тень: «Первый удар» (path_unique_1=True).
    Первая атака в каждой атакующей сессии (double_attack_used=False) даёт +20% к мощи.
    Возвращает (power, first_attack_bonus_applied).
    """
    if getattr(user, "path_unique_1", False) and not getattr(user, "double_attack_used", False):
        bonus_power = int(power * _SHADOW_FIRST_ATTACK_BONUS)
        return power + bonus_power, True
    return power, False


async def fight_district(
    session: AsyncSession,
    user: User,
    district_power: int,
    is_first_attack: bool = True,
) -> dict:
    """
    Бой с районом (бот).
    Возвращает {"win": bool, "is_crit": bool, "user_power": int, "district_power": int,
                "first_attack_bonus": bool}
    """
    from app.models.skill import UserMastery
    from sqlalchemy import select

    user_power, is_crit = await roll_crit(session, user)

    # Тень: «Первый удар» — первая атака +30% мощи
    first_attack_bonus = False
    if is_first_attack:
        user_power, first_attack_bonus = _apply_shadow_first_attack(user, user_power)

    # Бонус выносливости — можно побеждать врагов сильнее на X%
    mastery_result = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = mastery_result.scalar_one_or_none()
    endurance_bonus = 0
    if mastery:
        endurance_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        raw = endurance_levels.get(mastery.endurance, 0)
        endurance_bonus = int(raw * user.skill_path_bonus_multiplier)

    # Круговой донат «Дракон» круг 3: снижение входящего урона (защита атакующего)
    defense_bonus = getattr(user, "circ_defense_bonus", 0)
    if defense_bonus > 0:
        district_power = int(district_power * (1 - defense_bonus / 100))

    effective_threshold = int(district_power * (1 - endurance_bonus / 100))
    win = user_power >= effective_threshold

    return {
        "win": win,
        "is_crit": is_crit,
        "user_power": user_power,
        "district_power": district_power,
        "effective_threshold": effective_threshold,
        "first_attack_bonus": first_attack_bonus,
        "defense_bonus": defense_bonus,
    }


async def fight_player(
    session: AsyncSession,
    attacker: User,
    defender: User,
    is_first_attack: bool = True,
) -> dict:
    """
    PvP бой между двумя игроками.
    Возвращает {"win": bool, "is_crit": bool, "attacker_power": int, "defender_power": int,
                "first_attack_bonus": bool}
    """
    attacker_power, is_crit = await roll_crit(session, attacker)

    # Тень: «Первый удар» — первая атака +30% мощи
    first_attack_bonus = False
    if is_first_attack:
        attacker_power, first_attack_bonus = _apply_shadow_first_attack(attacker, attacker_power)

    defender_power = await get_effective_power(session, defender)

    # Круговой донат «Дракон» круг 3 (защитника): снижение входящего урона
    defense_bonus = getattr(defender, "circ_defense_bonus", 0)
    if defense_bonus > 0:
        attacker_power = int(attacker_power * (1 - defense_bonus / 100))

    # Круговой донат «Архангел» круг 5 (защитника): отражение урона
    reflect_pct = getattr(defender, "circ_reflect_pct", 0)
    reflected_power = 0
    if reflect_pct > 0:
        reflected_power = int(defender_power * reflect_pct / 100)
        defender_power += reflected_power

    win = attacker_power >= defender_power

    return {
        "win": win,
        "is_crit": is_crit,
        "attacker_power": attacker_power,
        "defender_power": defender_power,
        "effective_defense": defender_power,
        "first_attack_bonus": first_attack_bonus,
        "defense_bonus": defense_bonus,
        "reflected_power": reflected_power,
    }
