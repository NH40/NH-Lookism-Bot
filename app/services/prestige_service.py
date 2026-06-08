from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from app.models.user import User
from app.models.squad_member import SquadMember
from app.models.building import UserBuilding
from app.models.character import UserCharacter
from app.models.city import District, FistBot
from app.models.king_bot import KingBot
from app.models.skill import UserMastery, UserPathSkills
from app.models.potion import ActivePotion

# Убираем MAX_PRESTIGE = 10 и добавляем вверху:
from app.constants.prestige import (
    MAX_PRESTIGE,
    PRESTIGE_INCOME_BONUS_PER_LEVEL,
    PRESTIGE_RECRUIT_BONUS_PER_LEVEL,
    PRESTIGE_TRAIN_BONUS_PER_LEVEL,
    PRESTIGE_TICKET_BONUS_PER_LEVEL,
)
from app.config.game_balance import (
    DEFAULT_MAX_TICKETS,
    DEFAULT_TICKET_CHANCE,
    DEFAULT_INFLUENCE,
    EXTRA_SKILL_SLOTS_BASE,
)

class PrestigeService:

    def can_prestige(self, user: User) -> tuple[bool, str]:
        if user.phase != "emperor":
            return False, "Пробуждение доступно только Императорам"
        if user.prestige_level >= MAX_PRESTIGE:
            return False, f"Достигнут максимальный уровень ({MAX_PRESTIGE})"
        return True, ""

    async def _reset_progress(
        self,
        session: AsyncSession,
        user: User,
        keep_ui: bool = False,
        keep_progress: bool = False,
    ) -> None:
        """Сброс прогресса кроме донатов, пробуждений и достижений.

        keep_progress=True — при уничтожении банды: сохраняет ui_fragments,
        ui_level, mastery_points, UserMastery-статы, skill_path_points.
        keep_ui=True      — при престиже: сохраняет ui_fragments и ui_level.
        """
        user.phase = "gang"
        user.sector = None
        user.gang_city_id = None
        user.king_cities_count = 0
        user.fist_wins = 0
        user.fist_cities_count = 0
        user.nh_coins = 0
        user.card_dust = 0
        user.influence = DEFAULT_INFLUENCE
        user.combat_power = 0
        # Сбрасываем накопленный бонус от учителя; связь referred_by сохраняется,
        # шедулер пересчитает бонус от новой мощи учителя.
        from app.config.game_balance import REFERRAL_STUDENT_POWER_BONUS
        user.teacher_power_bonus = REFERRAL_STUDENT_POWER_BONUS if user.referred_by else 0
        user.business_path = None
        user.income_per_minute = 0
        user.income_bonus_percent = 0
        user.building_discount_percent = 0
        user.district_multiplier = 1.0
        user.tickets = 0
        user.max_tickets = DEFAULT_MAX_TICKETS
        user.ticket_chance = DEFAULT_TICKET_CHANCE
        user.recruit_count_bonus = 0
        user.double_recruit = False
        user.train_bonus_percent = 0
        user.train_quality_bonus = 0
        user.double_train = False
        user.double_attack = False
        user.double_attack_used = False
        user.extra_attack_count = 0

        # ── Путь и алхимия сбрасываются всегда ───────────────────────────
        user.skill_path = None
        user.skill_path_bonus_multiplier = 1.0
        user.skill_path_level = 0
        user.path_fragments = 0
        user.alchemy_fragments = 0
        user.extra_path_skill_slots = EXTRA_SKILL_SLOTS_BASE
        user.double_ticket = False
        user.path_awakened = False
        user.squad_power_bonus = 0
        user.all_cd_reduction = 0
        user.recruit_discount_percent = 0
        user.win_streak = 0
        user.truce_until = None
        user.truce_cd_until = None

        # ── Гений войны и бизнеса — прогрессионные, всегда сбрасываются ─
        user.war_points = 0
        user.war_genius_level = 0
        user.business_fragments = 0
        user.bonus_business_districts = 0
        user.business_genius_level = 0

        # Удаляем личный город бонусных районов
        from app.models.city import City
        bonus_city_row = await session.execute(
            select(City).where(City.phase == "business", City.owner_id == user.id)
        )
        bonus_city = bonus_city_row.scalar_one_or_none()
        if bonus_city:
            await session.execute(delete(District).where(District.city_id == bonus_city.id))
            await session.delete(bonus_city)

        # ── Клановые бонусы от апгрейдов (не донат) ─────────────────────
        user.clan_income_bonus = 0
        user.clan_ticket_bonus = 0
        user.clan_train_bonus = 0

        # ── Гений медицины: сбрасываем уровни если нет доната ───────────
        # reapply_all_titles ниже восстановит до 6 если есть ui_potion
        if not getattr(user, "med_genius_donat", False):
            user.mg_level_power     = 0
            user.mg_level_training  = 0
            user.mg_level_income    = 0
            user.mg_level_luck      = 0
            user.mg_level_influence = 0
            user.mg_level_raid_drop = 0

        # ── Очки мастерства и пути — только при полном сбросе ────────────
        if not keep_progress:
            user.mastery_points = 0
            user.skill_path_points = 0

        # ── УИ — сохраняется при престиже или при уничтожении банды ──────
        if not keep_ui and not keep_progress:
            from app.services.raid_service import raid_service as rs
            rs.reset_game_ui(user)
            user.ui_fragments = 0

        from app.services.market_service import market_service
        await market_service.cancel_all_user_listings(session, user.id)

        await session.execute(
            delete(SquadMember).where(SquadMember.user_id == user.id)
        )
        await session.execute(
            delete(UserBuilding).where(UserBuilding.user_id == user.id)
        )
        await session.execute(
            delete(UserCharacter).where(UserCharacter.user_id == user.id)
        )
        await session.execute(
            delete(ActivePotion).where(ActivePotion.user_id == user.id)
        )
        await session.execute(
            delete(District).where(District.owner_id == user.id)
        )
        await session.execute(
            delete(UserPathSkills).where(UserPathSkills.user_id == user.id)
        )
        await session.execute(
            delete(KingBot).where(KingBot.user_id == user.id)
        )
        await session.execute(
            delete(FistBot).where(FistBot.challenger_id == user.id)
        )
        from app.models.emperor_gang import EmperorGangRecord
        await session.execute(
            delete(EmperorGangRecord).where(EmperorGangRecord.user_id == user.id)
        )

        # ── Мастерство — только при полном сбросе ────────────────────────
        if not keep_progress:
            r = await session.execute(
                select(UserMastery).where(UserMastery.user_id == user.id)
            )
            mastery = r.scalar_one_or_none()
            if mastery:
                mastery.strength = 0
                mastery.speed = 0
                mastery.endurance = 0
                mastery.technique = 0

        # Сохраняем крафтовый УИ до reapply_all_titles (она сбрасывает ui_level через _reset_donat_bonuses)
        saved_ui_level = user.ui_level if (keep_ui or keep_progress) and not user.ui_is_donat else 0

        # Переприменяем донат-бонусы
        from app.services.title_service import title_service
        await title_service.reapply_all_titles(session, user)

        # Стелс сбрасываем ПОСЛЕ reapply — иначе активация path_unique_2 (донат)
        # внутри reapply снова включает shadow_stealth_active = True
        user.shadow_stealth_active = False

        # Восстанавливаем крафтовый УИ после сброса донат-бонусов
        if saved_ui_level > 0:
            from app.services.raid_service import raid_service as rs
            user.ui_level = saved_ui_level
            rs._apply_ui_level(user, saved_ui_level)

        # Сбрасываем несекретные достижения — игроки могут выполнить их заново
        from app.models.title import UserAchievement
        from app.data.titles import ACHIEVEMENT_MAP
        secret_ids = {a.achievement_id for a in ACHIEVEMENT_MAP.values() if a.secret}
        await session.execute(
            delete(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id.not_in(list(secret_ids)),
            )
        )

        await session.flush()

    async def do_prestige(self, session: AsyncSession, user: User) -> dict:
        ok, reason = self.can_prestige(user)
        if not ok:
            return {"ok": False, "reason": reason}

        user.prestige_level += 1
        user.prestige_income_bonus += PRESTIGE_INCOME_BONUS_PER_LEVEL
        user.prestige_recruit_bonus += PRESTIGE_RECRUIT_BONUS_PER_LEVEL
        user.prestige_train_bonus += PRESTIGE_TRAIN_BONUS_PER_LEVEL
        user.prestige_ticket_bonus += PRESTIGE_TICKET_BONUS_PER_LEVEL
        user.ticket_chance = min(getattr(user, "max_ticket_chance", 70), user.ticket_chance + 1)

        # При престиже — УИ и фрагменты сохраняются (keep_ui=True)
        await self._reset_progress(session, user, keep_ui=True)
        return {"ok": True, "level": user.prestige_level}

prestige_service = PrestigeService()