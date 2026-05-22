from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.skill import UserMastery
from app.data.skills import MASTERY_BY_ID


async def get_or_create_mastery(
    session: AsyncSession, user_id: int
) -> UserMastery:
    result = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user_id)
    )
    mastery = result.scalar_one_or_none()
    if not mastery:
        mastery = UserMastery(user_id=user_id)
        session.add(mastery)
        await session.flush()
    return mastery


async def upgrade_mastery(
    session: AsyncSession, user: User, skill_id: str
) -> dict:
    cfg = MASTERY_BY_ID.get(skill_id)
    if not cfg:
        return {"ok": False, "reason": "Навык не найден"}

    mastery = await get_or_create_mastery(session, user.id)
    current_level = getattr(mastery, skill_id, 0)
    next_level = current_level + 1

    if next_level >= len(cfg.levels):
        return {"ok": False, "reason": "Максимальный уровень"}

    level_cfg = cfg.levels[next_level]
    if user.nh_coins < level_cfg.cost:
        return {"ok": False, "reason": f"Нужно {level_cfg.cost:,} NHCoin"}

    user.nh_coins -= level_cfg.cost
    user.coins_spent += level_cfg.cost
    setattr(mastery, skill_id, next_level)

    # Применяем бонус к User
    await _apply_mastery_bonus(session, user, skill_id, next_level)
    await session.flush()

    return {
        "ok": True,
        "skill": skill_id,
        "new_level": next_level,
        "bonus": level_cfg.bonus,
    }


async def _apply_mastery_bonus(
    session: AsyncSession, user: User, skill_id: str, level: int
) -> None:
    cfg = MASTERY_BY_ID[skill_id]
    bonus = cfg.levels[level].bonus
    prev_bonus = cfg.levels[level - 1].bonus if level > 0 else 0
    delta = bonus - prev_bonus

    if skill_id == "technique":
        # Техника влияет на тренировку И доход
        user.train_bonus_percent += delta
        user.income_bonus_percent += delta
        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
    elif skill_id == "strength":
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
