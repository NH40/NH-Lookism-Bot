from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


def reset_donat_bonuses(user: User) -> None:
    user.ultra_instinct = False
    user.true_ultra_instinct = False
    user.double_recruit = False
    user.double_attack = False
    user.double_ticket = False
    user.extra_attack_count = 0
    user.ticket_cd_reduction = 0
    user.recruit_count_bonus = 0
    user.train_bonus_percent = 0
    user.train_quality_bonus = 0
    user.income_bonus_percent = 0
    user.building_discount_percent = 0
    user.max_tickets = 3
    user.ticket_chance = 25
    user.skill_path_bonus_multiplier = 1.0
    user.extra_path_skill_slots = 1
    user.max_ticket_chance = 70
    user.squad_power_bonus = 0
    user.ui_is_donat = False
    user.ui_level = 0
    user.ui_auto_recruit = False
    user.ui_auto_train = False
    user.ui_auto_ticket = False
    user.ui_auto_pull = False
    user.donat_ui_potion = False
    user.ui_auto_potion = False
    user.donat_duel_cd = False


async def apply_title_bonus(
    session: AsyncSession, user: User, title_id: str
) -> None:
    if title_id == "fist_power":
        pass
    elif title_id == "romantic_recruit":
        user.recruit_count_bonus += 100
    elif title_id == "great_influence":
        pass
    elif title_id == "genius_training":
        user.train_bonus_percent += 70
    elif title_id == "genius_business":
        user.income_bonus_percent += 50
    elif title_id == "genius_weapon":
        pass
    elif title_id == "genius_combat":
        user.skill_path_bonus_multiplier = max(
            user.skill_path_bonus_multiplier, 1.20
        )
    elif title_id == "genius_hacking":
        user.recruit_count_bonus += 30
    elif title_id == "genius_medicine":
        user.skill_path_bonus_multiplier = max(
            user.skill_path_bonus_multiplier, 1.30
        )
    elif title_id == "genius_scale":
        user.train_bonus_percent += 15
        user.income_bonus_percent += 15
        user.recruit_count_bonus += 15
    elif title_id == "legend_1gen":
        pass
    elif title_id == "monster_training":
        user.train_bonus_percent += 100
    elif title_id == "reverse_eyes":
        pass
    elif title_id == "selection":
        pass
    elif title_id == "manager_fav":
        user.ticket_chance = min(getattr(user, "max_ticket_chance", 70), user.ticket_chance + 10)
    elif title_id == "concentration":
        pass
    elif title_id == "focus":
        pass
    elif title_id == "ui_title":
        from app.services.raid_service import raid_service as rs
        rs.apply_donat_ui(user)
        if user.donat_ui_potion and user.ui_auto_potion:
            from app.services.potion_service import potion_service
            await potion_service.buy_missing(session, user)
    elif title_id == "ui_potion":
        user.donat_ui_potion = True
        if user.ui_auto_potion:
            from app.services.potion_service import potion_service
            await potion_service.buy_missing(session, user)
    elif title_id == "duel_cd":
        user.donat_duel_cd = True
    elif title_id == "rom_extra_skills":
        from app.config.game_balance import EXTRA_SKILL_SLOTS_WITH_TITLE
        user.extra_path_skill_slots = EXTRA_SKILL_SLOTS_WITH_TITLE
    elif title_id == "rom_max_chance":
        user.max_ticket_chance = 90


def apply_set_bonus(user: User, set_id: str) -> None:
    if set_id == "strongest_0gen":
        from app.config.game_balance import EXTRA_SKILL_SLOTS_WITH_TITLE
        user.influence = int(user.influence * 2.0)
        user.extra_path_skill_slots = EXTRA_SKILL_SLOTS_WITH_TITLE
        user.max_ticket_chance = 90
        user.ticket_chance = min(getattr(user, "max_ticket_chance", 70), user.ticket_chance + 5)
        user.double_recruit = True
        user.double_ticket = True
    elif set_id == "genius_maker":
        user.train_bonus_percent = int(user.train_bonus_percent * 1.20)
        user.income_bonus_percent = int(user.income_bonus_percent * 1.20)
        user.recruit_count_bonus = int(user.recruit_count_bonus * 1.20)
        if user.skill_path_bonus_multiplier > 1.0:
            user.skill_path_bonus_multiplier = round(user.skill_path_bonus_multiplier * 1.20, 4)
    elif set_id == "monster":
        user.double_attack = True
        if user.skill_path == "monster":
            user.extra_attack_count = 2
        else:
            user.extra_attack_count = 1
    elif set_id == "flow":
        user.ticket_cd_reduction += 15
    elif set_id == "ui_set":
        user.ultra_instinct = True


async def rebuild_base_bonuses(
    session: AsyncSession, user: User
) -> None:
    """Восстанавливает не-донат бонусы после _reset_donat_bonuses."""
    from sqlalchemy import select as sa_select
    from app.models.skill import UserMastery, UserPathSkills
    from app.data.skills import MASTERY_BY_ID, PATH_SKILLS

    multiplier = user.skill_path_bonus_multiplier

    mastery = await session.scalar(
        sa_select(UserMastery).where(UserMastery.user_id == user.id)
    )
    if mastery and mastery.technique > 0:
        tech_cfg = MASTERY_BY_ID.get("technique")
        if tech_cfg and mastery.technique < len(tech_cfg.levels):
            bonus = tech_cfg.levels[mastery.technique].bonus
            user.income_bonus_percent += int(bonus * multiplier)
            user.train_bonus_percent += int(bonus * multiplier)

    bought_r = await session.execute(
        sa_select(UserPathSkills.skill_id).where(
            UserPathSkills.user_id == user.id
        )
    )
    bought_ids = set(bought_r.scalars().all())
    if bought_ids:
        all_skills_map: dict = {}
        for path_skills in PATH_SKILLS.values():
            for s in path_skills:
                all_skills_map[s.skill_id] = s
        for skill_id in bought_ids:
            skill = all_skills_map.get(skill_id)
            if not skill:
                continue
            for field, value in skill.effect.items():
                if isinstance(value, float):
                    continue
                if isinstance(value, bool):
                    setattr(user, field, value)
                else:
                    current = getattr(user, field, 0)
                    setattr(user, field, current + int(value * multiplier))

    _income_keys: dict[str, int] = {
        "coins_and_income": 5,
        "coins_and_income_2": 2,
        "coins_and_income_3": 3,
        "coins_and_income_7": 7,
        "coins_and_income_10": 10,
        "coins_and_income_15": 15,
        "quest_reward": 3,
    }
    from sqlalchemy import select as sa_select2
    from app.models.title import UserAchievement
    from app.data.titles import ACHIEVEMENT_MAP
    claimed_r = await session.execute(
        sa_select2(UserAchievement.achievement_id).where(
            UserAchievement.user_id == user.id,
            UserAchievement.claimed == True,
        )
    )
    for ach_id in claimed_r.scalars().all():
        ach = ACHIEVEMENT_MAP.get(ach_id)
        if ach and ach.bonus_key in _income_keys:
            user.income_bonus_percent += _income_keys[ach.bonus_key]
