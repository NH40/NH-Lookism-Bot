import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.skill import UserPathSkills
from app.data.skills import PATH_SKILLS, PATH_SYNERGIES
from app.constants.raid import (
    PATH_LEVEL_COSTS, PATH_LEVEL_MAX, PATH_LEVEL_BONUSES, PATH_AWAKENING_BONUSES,
)


def _all_path_skills_map() -> dict:
    result = {}
    for path_skills in PATH_SKILLS.values():
        for s in path_skills:
            result[s.skill_id] = s
    return result


async def choose_path(
    session: AsyncSession, user: User, path: str
) -> dict:
    if user.skill_path:
        return {"ok": False, "reason": f"Путь уже выбран: {user.skill_path}"}
    if path not in PATH_SKILLS:
        return {"ok": False, "reason": "Неизвестный путь"}
    user.skill_path = path
    await session.flush()
    return {"ok": True, "path": path}


async def upgrade_path_level(session: AsyncSession, user: User) -> dict:
    if not user.skill_path:
        return {"ok": False, "reason": "Сначала выбери путь"}

    current = getattr(user, "skill_path_level", 0)
    if current >= PATH_LEVEL_MAX:
        return {"ok": False, "reason": "Максимальный уровень пути достигнут"}

    cost = PATH_LEVEL_COSTS[current]
    path_frags = getattr(user, "path_fragments", 0)
    if path_frags < cost:
        return {"ok": False, "reason": f"Нужно {cost} 🔷 фрагментов Пути (у вас {path_frags})"}

    user.path_fragments -= cost
    user.skill_path_level = current + 1

    bonuses = PATH_LEVEL_BONUSES.get(user.skill_path, {})
    for field, delta in bonuses.items():
        setattr(user, field, getattr(user, field, 0) + delta)

    from app.services.business_service import business_service
    await business_service._recalc_income(session, user)
    from app.repositories.squad_repo import squad_repo
    await squad_repo.update_user_combat_power(session, user)
    await session.flush()

    return {"ok": True, "new_level": user.skill_path_level, "cost": cost, "bonuses": bonuses}


async def _apply_synergy(
    session: AsyncSession, user: User, foreign_path: str, get_path_skills_bought_fn
) -> dict | None:
    """Apply synergy bonus if this is the first skill from foreign_path. Returns synergy info or None."""
    synergy = PATH_SYNERGIES.get((user.skill_path, foreign_path))
    if not synergy:
        return None

    all_map = _all_path_skills_map()
    bought = await get_path_skills_bought_fn(session, user.id)
    already_have = sum(1 for sid in bought if all_map.get(sid) and all_map[sid].path == foreign_path)
    if already_have > 0:
        return None  # синергия уже применена ранее

    for field, value in synergy["effect"].items():
        setattr(user, field, getattr(user, field, 0) + value)
    return synergy


async def _check_and_awaken(session: AsyncSession, user: User, get_path_skills_bought_fn) -> bool:
    """Awaken the path if all main skills are bought. Returns True if just awakened."""
    if getattr(user, "path_awakened", False) or not user.skill_path:
        return False

    bought = set(await get_path_skills_bought_fn(session, user.id))
    main_ids = {s.skill_id for s in PATH_SKILLS.get(user.skill_path, [])}
    if not main_ids.issubset(bought):
        return False

    user.path_awakened = True
    bonuses = PATH_AWAKENING_BONUSES.get(user.skill_path, {})
    for field, value in bonuses.items():
        if isinstance(value, float):
            setattr(user, field, getattr(user, field, 1.0) * value)
        else:
            setattr(user, field, getattr(user, field, 0) + value)

    from app.services.business_service import business_service
    await business_service._recalc_income(session, user)
    from app.repositories.squad_repo import squad_repo
    await squad_repo.update_user_combat_power(session, user)
    await session.flush()
    return True


async def get_path_skills_bought(
    session: AsyncSession, user_id: int
) -> list[str]:
    result = await session.execute(
        select(UserPathSkills.skill_id).where(
            UserPathSkills.user_id == user_id
        )
    )
    return result.scalars().all()


async def get_extra_path_skills_count(
    session: AsyncSession, user: User
) -> int:
    """Count skills owned from other paths (extra skills)."""
    bought = await get_path_skills_bought(session, user.id)
    main_ids = {s.skill_id for s in PATH_SKILLS.get(user.skill_path or "", [])}
    return sum(1 for sid in bought if sid not in main_ids)


def _update_extra_attack(user: User) -> None:
    """extra_attack_count: 1 = 2 атаки, 2 = 3 атаки."""
    # Считаем сколько источников double_attack
    # Проверяется снаружи через title_service при выдаче доната
    # Здесь просто устанавливаем минимум 1
    if user.extra_attack_count < 1:
        user.extra_attack_count = 1


async def _apply_path_skill(session: AsyncSession, user: User, skill) -> None:
    multiplier = user.skill_path_bonus_multiplier
    for field, value in skill.effect.items():
        if isinstance(value, bool):
            setattr(user, field, value)
        elif isinstance(value, float):
            current = getattr(user, field, 1.0)
            setattr(user, field, current * value)
        else:
            current = getattr(user, field, 0)
            bonus = int(value * multiplier)
            setattr(user, field, current + bonus)

    # double_attack — проверяем комбо
    if user.double_attack:
        _update_extra_attack(user)

    # Пересчёты
    from app.services.business_service import business_service
    await business_service._recalc_income(session, user)
    from app.repositories.squad_repo import squad_repo
    await squad_repo.update_user_combat_power(session, user)
    await session.flush()


async def buy_path_skill(
    session: AsyncSession, user: User, skill_id: str
) -> dict:
    if not user.skill_path:
        return {"ok": False, "reason": "Сначала выберите путь"}

    skills = PATH_SKILLS.get(user.skill_path, [])
    skill = next((s for s in skills if s.skill_id == skill_id), None)
    if not skill:
        return {"ok": False, "reason": "Навык не найден в вашем пути"}

    # Проверяем — не куплен ли уже
    result = await session.execute(
        select(UserPathSkills).where(
            UserPathSkills.user_id == user.id,
            UserPathSkills.skill_id == skill_id,
        )
    )
    if result.scalar_one_or_none():
        return {"ok": False, "reason": "Навык уже куплен"}

    # Проверяем уровень пути
    required_level = getattr(skill, "min_path_level", 0)
    current_path_level = getattr(user, "skill_path_level", 0)
    if current_path_level < required_level:
        return {"ok": False, "reason": f"Нужен уровень пути {required_level} (у вас {current_path_level})"}

    if user.skill_path_points < skill.cost:
        return {
            "ok": False,
            "reason": f"Нужно {skill.cost} очков пути (у вас {user.skill_path_points})",
        }

    user.skill_path_points -= skill.cost

    record = UserPathSkills(user_id=user.id, skill_id=skill_id)
    session.add(record)
    await session.flush()

    await _apply_path_skill(session, user, skill)

    # Проверяем пробуждение
    awakened = await _check_and_awaken(session, user, get_path_skills_bought)
    return {"ok": True, "skill": skill.name, "awakened": awakened}


async def spin_for_random_extra_skill(
    session: AsyncSession, user: User
) -> dict:
    if not user.skill_path:
        return {"ok": False, "reason": "Сначала выбери путь!"}

    slots = getattr(user, "extra_path_skill_slots", 1)
    extra_count = await get_extra_path_skills_count(session, user)
    if extra_count >= slots:
        return {"ok": False, "reason": f"Слоты слияния заполнены ({extra_count}/{slots})"}

    bought = set(await get_path_skills_bought(session, user.id))
    other_paths = [p for p in PATH_SKILLS if p != user.skill_path]
    candidates = [
        s for p in other_paths
        for s in PATH_SKILLS[p]
        if s.skill_id not in bought
    ]
    if not candidates:
        return {"ok": False, "reason": "Все навыки других путей уже получены!"}

    skill = random.choice(candidates)
    # Синергия — до добавления записи (считаем ещё без нового навыка)
    synergy = await _apply_synergy(session, user, skill.path, get_path_skills_bought)
    record = UserPathSkills(user_id=user.id, skill_id=skill.skill_id)
    session.add(record)
    await _apply_path_skill(session, user, skill)
    return {
        "ok": True,
        "skill": skill.name,
        "emoji": skill.emoji,
        "description": skill.description,
        "path": skill.path,
        "synergy": synergy,
    }


# ── Публичные обёртки (используются SkillService в base.py) ──────────────────

async def apply_synergy(session: AsyncSession, user: User, foreign_path: str) -> dict | None:
    """Публичная обёртка: синергия без передачи fn-аргумента."""
    return await _apply_synergy(session, user, foreign_path, get_path_skills_bought)


async def check_and_awaken(session: AsyncSession, user: User) -> bool:
    """Публичная обёртка: пробуждение без передачи fn-аргумента."""
    return await _check_and_awaken(session, user, get_path_skills_bought)


apply_path_skill = _apply_path_skill
update_extra_attack = _update_extra_attack


async def buy_extra_path_skill(
    session: AsyncSession, user: User, skill_id: str
) -> dict:
    if not user.skill_path:
        return {"ok": False, "reason": "Сначала выбери путь!"}

    # Limit check
    slots = getattr(user, "extra_path_skill_slots", 0)
    extra_count = await get_extra_path_skills_count(session, user)
    if extra_count >= slots:
        return {
            "ok": False,
            "reason": f"Все слоты заняты ({extra_count}/{slots}). Нужен донат-титул!",
        }

    all_skills = _all_path_skills_map()
    skill = all_skills.get(skill_id)
    if not skill or skill.path == user.skill_path:
        return {"ok": False, "reason": "Навык не найден или принадлежит вашему пути"}

    bought = set(await get_path_skills_bought(session, user.id))
    if skill_id in bought:
        return {"ok": False, "reason": "Навык уже куплен"}

    cost = skill.cost * 5
    if user.skill_path_points < cost:
        return {
            "ok": False,
            "reason": f"Нужно {cost} 💎 очков пути (у вас {user.skill_path_points})",
        }

    user.skill_path_points -= cost
    # Синергия — до добавления записи
    synergy = await _apply_synergy(session, user, skill.path, get_path_skills_bought)
    record = UserPathSkills(user_id=user.id, skill_id=skill_id)
    session.add(record)
    await _apply_path_skill(session, user, skill)
    return {"ok": True, "skill": skill.name, "cost": cost, "synergy": synergy}
