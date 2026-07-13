from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.config.game_balance import DEFAULT_MAX_TICKETS


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
    user.max_tickets = DEFAULT_MAX_TICKETS
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
    user.donat_duel_cd = False
    user.all_cd_reduction = 0
    user.trainer_cd_reduction = 0
    user.med_genius_donat = False
    # Уровни 1-5 заработаны фрагментами — НЕ сбрасываем.
    # Уровень 6 — только от доната — откатываем до 5 если был 6.
    for _field in ("mg_level_power", "mg_level_training", "mg_level_income",
                   "mg_level_luck", "mg_level_influence", "mg_level_raid_drop"):
        if getattr(user, _field, 0) >= 6:
            setattr(user, _field, 5)

    # Откатываем аддитивный бонус влияния от сета strongest_0gen.
    # Используем getattr для совместимости с объектами без этого поля.
    prev_bonus = getattr(user, "influence_donat_bonus", 0) or 0
    if prev_bonus > 0:
        user.influence = max(100, user.influence - prev_bonus)
        user.influence_donat_bonus = 0


async def apply_title_bonus(
    session: AsyncSession, user: User, title_id: str
) -> None:
    if title_id == "fist_power":
        user.squad_power_bonus += 20
    elif title_id == "romantic_recruit":
        user.recruit_count_bonus += 40
    elif title_id == "great_influence":
        user.influence = max(3000, user.influence)
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
        user.all_cd_reduction = getattr(user, "all_cd_reduction", 0) + 10
    elif title_id == "focus":
        user.all_cd_reduction = getattr(user, "all_cd_reduction", 0) + 20
    elif title_id == "raid_cd":
        user.all_cd_reduction = getattr(user, "all_cd_reduction", 0) + 20
    elif title_id == "ui_title":
        from app.services.raid_service import raid_service as rs
        rs.apply_donat_ui(user)
    elif title_id == "ui_potion":
        user.med_genius_donat = True
        # Донат = максимальный тир всех зелий
        user.mg_level_power     = 6
        user.mg_level_training  = 6
        user.mg_level_income    = 6
        user.mg_level_luck      = 6
        user.mg_level_influence = 6
        user.mg_level_raid_drop = 6
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
        # Аддитивный бонус +60% к текущему базовому влиянию.
        # Сохраняем прибавку в influence_donat_bonus, чтобы reset_donat_bonuses
        # мог точно её вычесть — иначе каждый reapply_all_titles множил бы
        # значение на 1.6 ещё раз (экспоненциальный рост).
        influence_add = int(user.influence * 0.6)
        user.influence += influence_add
        user.influence_donat_bonus = influence_add
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
        user.all_cd_reduction += 15
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

    # double_attack без extra_attack_count (например, только mon_dattack без
    # mon_extra_atk1/2/3) должен давать минимум 1 бонусную атаку — иначе
    # следующий reapply_all_titles обнулит extra_attack_count и игрок
    # молча теряет одну атаку до пересчёта в _handle_attack_cd.
    if user.double_attack:
        from app.services.skill.path import _update_extra_attack
        _update_extra_attack(user)

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
