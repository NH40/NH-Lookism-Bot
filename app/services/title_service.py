from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.user import User
from app.models.title import UserDonatTitle, UserAchievement
from app.data.titles import (
    DONAT_TITLE_MAP, DONAT_SET_MAP, DONAT_SETS, DONAT_TITLES,
    ACHIEVEMENTS, ACHIEVEMENT_MAP,
)


class TitleService:

    # ── Донат-титулы ────────────────────────────────────────────────────────

    async def grant_title(
        self, session: AsyncSession, user: User,
        title_id: str, admin_tg_id: int | None = None
    ) -> dict:
        cfg = DONAT_TITLE_MAP.get(title_id)
        if not cfg:
            return {"ok": False, "reason": "Титул не найден"}

        result = await session.execute(
            select(UserDonatTitle).where(
                UserDonatTitle.user_id == user.id,
                UserDonatTitle.title_id == title_id,
            )
        )
        if result.scalar_one_or_none():
            return {"ok": False, "reason": "Титул уже выдан"}

        record = UserDonatTitle(
            user_id=user.id,
            title_id=title_id,
            set_id=cfg.set_id,
            granted_by=admin_tg_id,
        )
        session.add(record)
        await session.flush()

        await self._apply_title_bonus(session, user, title_id)
        await self._check_set_completion(session, user, cfg.set_id)
        return {"ok": True, "title": cfg.name}

    async def revoke_title(
        self, session: AsyncSession, user: User, title_id: str
    ) -> dict:
        await session.execute(
            delete(UserDonatTitle).where(
                UserDonatTitle.user_id == user.id,
                UserDonatTitle.title_id == title_id,
            )
        )
        await session.flush()
        await self.reapply_all_titles(session, user)
        return {"ok": True}

    async def grant_all_titles(
        self, session: AsyncSession, user: User, admin_tg_id: int
    ) -> int:
        count = 0
        for title in DONAT_TITLES:
            result = await self.grant_title(
                session, user, title.title_id, admin_tg_id
            )
            if result["ok"]:
                count += 1
        return count

    async def revoke_all_titles(
        self, session: AsyncSession, user: User
    ) -> None:
        await session.execute(
            delete(UserDonatTitle).where(UserDonatTitle.user_id == user.id)
        )
        await session.flush()
        await self.reapply_all_titles(session, user)

    async def get_user_titles(
        self, session: AsyncSession, user_id: int
    ) -> list[str]:
        result = await session.execute(
            select(UserDonatTitle.title_id).where(
                UserDonatTitle.user_id == user_id
            )
        )
        return result.scalars().all()

    async def reapply_all_titles(
        self, session: AsyncSession, user: User
    ) -> None:
        self._reset_donat_bonuses(user)
        title_ids = await self.get_user_titles(session, user.id)
        for title_id in title_ids:
            await self._apply_title_bonus(session, user, title_id)
        # Проверяем все сеты
        owned = set(title_ids)
        for s in DONAT_SETS:
            titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == s.set_id]
            if all(tid in owned for tid in titles_in_set):
                self._apply_set_bonus(user, s.set_id)

        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        await session.flush()

    def _reset_donat_bonuses(self, user: User) -> None:
        user.ultra_instinct = False
        user.double_recruit = False
        user.double_attack = False
        user.extra_attack_count = 0
        user.ticket_cd_reduction = 0
        user.recruit_count_bonus = 0
        user.train_bonus_percent = 0
        user.income_bonus_percent = 0
        user.max_tickets = 3
        user.ticket_chance = 25
        user.skill_path_bonus_multiplier = 1.0

    async def _apply_title_bonus(
        self, session: AsyncSession, user: User, title_id: str
    ) -> None:
        # Применяем бонусы по title_id
        if title_id == "fist_power":
            pass  # mult применяется в squad_repo
        elif title_id == "romantic_recruit":
            user.recruit_count_bonus += 100
        elif title_id == "great_influence":
            pass  # проверяется при бою
        elif title_id == "genius_training":
            user.train_bonus_percent += 70
        elif title_id == "genius_business":
            user.income_bonus_percent += 50
        elif title_id == "genius_weapon":
            pass  # mult в squad_repo
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
            pass  # крит в combat_service
        elif title_id == "monster_training":
            user.train_bonus_percent += 100
        elif title_id == "reverse_eyes":
            user.ticket_cd_reduction += 30
        elif title_id == "selection":
            pass  # влияет на веса гачи
        elif title_id == "manager_fav":
            user.ticket_chance = min(95, user.ticket_chance + 10)
        elif title_id == "concentration":
            user.ticket_cd_reduction += 30
        elif title_id == "focus":
            pass  # КД вербовки/тренировки — применяется в squad_service
        elif title_id == "ui_title":
            user.ultra_instinct = True
            user.max_tickets += 3

        # Обновляем extra_attack_count
        if user.double_attack:
            if user.extra_attack_count < 1:
                user.extra_attack_count = 1

    async def _check_set_completion(
        self, session: AsyncSession, user: User, set_id: str
    ) -> None:
        titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
        owned = set(await self.get_user_titles(session, user.id))
        if all(tid in owned for tid in titles_in_set):
            self._apply_set_bonus(user, set_id)
            await session.flush()

    def _apply_set_bonus(self, user: User, set_id: str) -> None:
        if set_id == "strongest_0gen":
            user.influence = int(user.influence * 2.0)
            user.ticket_chance = min(95, user.ticket_chance + 5)
            user.double_recruit = True
        elif set_id == "genius_maker":
            # Все баффы гениев ×1.20 — уже применены через _apply_title_bonus
            # Дополнительный бонус сета
            user.train_bonus_percent = int(user.train_bonus_percent * 1.20)
            user.income_bonus_percent = int(user.income_bonus_percent * 1.20)
            user.recruit_count_bonus = int(user.recruit_count_bonus * 1.20)
        elif set_id == "monster":
            # Мощь ×2 — в squad_repo, double_attack
            user.double_attack = True
            if user.extra_attack_count < 1:
                user.extra_attack_count = 1
            # Если ещё и путь монстра — 3 атаки
            if user.skill_path == "monster":
                user.extra_attack_count = 2
        elif set_id == "flow":
            # Все КД -15% дополнительно — через ticket_cd_reduction
            user.ticket_cd_reduction += 15

    # ── Достижения ──────────────────────────────────────────────────────────

    async def check_achievements(
        self, session: AsyncSession, user: User
    ) -> list[dict]:
        granted = []
        for ach in ACHIEVEMENTS:
            already = await session.execute(
                select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == ach.achievement_id,
                    UserAchievement.claimed == True,
                )
            )
            if already.scalar_one_or_none():
                continue
            if await self._check_condition_new(session, user, ach):
                await self._grant_achievement_new(session, user, ach)
                granted.append({
                    "name": ach.name,
                    "bonus_description": ach.bonus_description,
                    "coins": ach.bonus_value if "coins" in ach.bonus_key else 0,
                })
        if granted:
            from app.services.business_service import business_service
            await business_service._recalc_income(session, user)
        return granted

    async def _check_condition_new(
        self, session: AsyncSession, user: User, ach
    ) -> bool:
        key = ach.condition_key
        val = ach.condition_value
        if key == "combat_power":
            return user.combat_power >= val
        elif key == "phase_reached":
            order = {"gang": 0, "king": 1, "fist": 2, "emperor": 3}
            required = {1: "king", 2: "fist", 3: "emperor"}
            req = required.get(val)
            return bool(req and order.get(user.phase, 0) >= order.get(req, 99))
        elif key == "fist_cities_count":
            return user.fist_cities_count >= val
        elif key == "top_rank":
            from app.repositories.user_repo import user_repo
            rank = await user_repo.get_rank_by_power(session, user.id)
            return rank <= val
        elif key == "coins_spent":
            return user.coins_spent >= val
        elif key == "total_wins":
            return user.total_wins >= val
        elif key == "auction_wins":
            return user.auction_wins >= val
        elif key == "settings_opened":
            return user.settings_opened >= val
        elif key == "unique_chars":
            from sqlalchemy import func
            from app.models.character import UserCharacter
            count = await session.scalar(
                select(func.count(UserCharacter.id)).where(
                    UserCharacter.user_id == user.id
                )
            )
            return (count or 0) >= val
        return False

    async def _grant_achievement_new(
        self, session: AsyncSession, user: User, ach
    ) -> None:
        from datetime import datetime, timezone
        record = UserAchievement(
            user_id=user.id,
            achievement_id=ach.achievement_id,
            claimed=True,
            claimed_at=datetime.now(timezone.utc),
        )
        session.add(record)

        key = ach.bonus_key
        val = ach.bonus_value

        if key == "none":
            pass
        elif key == "coins":
            user.nh_coins += val
        elif key == "path_points":
            user.skill_path_points += val
        elif key == "coins_and_income":
            user.nh_coins += val
            user.income_bonus_percent += 5
        elif key == "coins_and_income_2":
            user.nh_coins += val
            user.income_bonus_percent += 2
        elif key == "coins_and_income_3":
            user.nh_coins += val
            user.income_bonus_percent += 3
        elif key == "coins_and_income_7":
            user.nh_coins += val
            user.income_bonus_percent += 7
        elif key == "coins_and_income_10":
            user.nh_coins += val
            user.income_bonus_percent += 10
        elif key == "coins_and_income_15":
            user.nh_coins += val
            user.income_bonus_percent += 15
        elif key == "quest_reward":
            user.nh_coins += val
            user.income_bonus_percent += 3
            # Выдаём случайного персонажа
            from app.services.deck_service import deck_service
            if user.tickets <= 0:
                user.tickets = 1
            await deck_service.pull(session, user)

        await session.flush()


title_service = TitleService()