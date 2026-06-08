from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.user import User
from app.models.title import UserDonatTitle, UserAchievement
from app.data.titles import (
    DONAT_TITLE_MAP, DONAT_SETS, DONAT_TITLES,
    ACHIEVEMENTS, ACHIEVEMENT_MAP,
)
from app.services.title.bonuses import (
    reset_donat_bonuses,
    apply_title_bonus,
    apply_set_bonus,
    rebuild_base_bonuses,
)
import app.services.title.sets as _sets


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

        await apply_title_bonus(session, user, title_id)
        await self._check_set_completion(session, user, cfg.set_id)

        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

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
        return await _sets.grant_all_titles(session, user, admin_tg_id, self.grant_title)

    async def revoke_set(
        self, session: AsyncSession, user: User, set_id: str
    ) -> int:
        return await _sets.revoke_set(session, user, set_id, self.reapply_all_titles)

    async def revoke_all_titles(
        self, session: AsyncSession, user: User
    ) -> None:
        await _sets.revoke_all_titles(session, user, self.reapply_all_titles)

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
        reset_donat_bonuses(user)
        title_ids = await self.get_user_titles(session, user.id)
        for title_id in title_ids:
            await apply_title_bonus(session, user, title_id)

        owned = set(title_ids)
        for s in DONAT_SETS:
            titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == s.set_id]
            if all(tid in owned for tid in titles_in_set):
                apply_set_bonus(user, s.set_id)

        await rebuild_base_bonuses(session, user)

        # Круговые донаты: пересчитываем поверх готовых титульных бонусов
        from app.services.circular_donat_service import rebuild_circular_bonuses
        await rebuild_circular_bonuses(session, user)

        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        await session.flush()

    async def has_set(
        self, session: AsyncSession, user_id: int, set_id: str
    ) -> bool:
        return await _sets.has_set(session, user_id, set_id)

    # kept for internal use / backward compat
    def _reset_donat_bonuses(self, user: User) -> None:
        reset_donat_bonuses(user)

    async def _apply_title_bonus(
        self, session: AsyncSession, user: User, title_id: str
    ) -> None:
        await apply_title_bonus(session, user, title_id)

    def _apply_set_bonus(self, user: User, set_id: str) -> None:
        apply_set_bonus(user, set_id)

    async def _rebuild_base_bonuses(
        self, session: AsyncSession, user: User
    ) -> None:
        await rebuild_base_bonuses(session, user)

    async def _check_set_completion(
        self, session: AsyncSession, user: User, set_id: str
    ) -> None:
        titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
        owned = set(await self.get_user_titles(session, user.id))
        if all(tid in owned for tid in titles_in_set):
            apply_set_bonus(user, set_id)
            await session.flush()

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
            if already.scalars().first():
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
        elif key == "king_cities_count":
            return user.king_cities_count >= val
        elif key == "prestige_level":
            return user.prestige_level >= val
        elif key == "mastery_points":
            return user.mastery_points >= val
        elif key == "achievements_count":
            from sqlalchemy import func
            from app.models.title import UserAchievement
            exclude = {"all_achievements", "absolute"}
            eligible = [a.achievement_id for a in ACHIEVEMENTS if not a.secret and a.achievement_id not in exclude]
            count = await session.scalar(
                select(func.count(UserAchievement.id)).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.claimed == True,
                    UserAchievement.achievement_id.in_(eligible),
                )
            )
            return (count or 0) >= val
        elif key == "achievements_count_all":
            from sqlalchemy import func
            from app.models.title import UserAchievement
            eligible = [a.achievement_id for a in ACHIEVEMENTS if a.achievement_id != "absolute"]
            count = await session.scalar(
                select(func.count(UserAchievement.id)).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.claimed == True,
                    UserAchievement.achievement_id.in_(eligible),
                )
            )
            return (count or 0) >= val
        elif key == "raid_boss_wins":
            return (user.raid_boss_wins or 0) >= val
        elif key == "total_statists_recruited":
            return (user.total_statists_recruited or 0) >= val
        elif key == "daily_quests_completed":
            return (user.daily_quests_completed or 0) >= val
        elif key == "market_sells":
            return (user.market_sells or 0) >= val
        elif key == "ui_level_max":
            # достигается при ui_level >= val ИЛИ донатный УИ (уже максимальный)
            return user.ui_is_donat or (user.ui_level or 0) >= val
        elif key == "med_genius_max":
            # все 6 зелий >= val (5) ИЛИ донатный Гений медицины
            if user.med_genius_donat:
                return True
            mg_fields = [
                "mg_level_power", "mg_level_training", "mg_level_income",
                "mg_level_luck", "mg_level_influence", "mg_level_raid_drop",
            ]
            return all((getattr(user, f, 0) or 0) >= val for f in mg_fields)
        elif key == "any_rank_complete":
            # Проверяем есть ли хотя бы одна редкость, все персонажи которой собраны
            from app.data.characters import CHARACTERS
            from app.models.character import UserCharacter
            from collections import defaultdict
            # Группируем нужные имена по рангу
            rank_names: dict[str, set] = defaultdict(set)
            for c in CHARACTERS:
                rank_names[c["rank"]].add(c["name"])
            # Получаем все character_id пользователя
            result = await session.execute(
                select(UserCharacter.character_id).where(
                    UserCharacter.user_id == user.id
                )
            )
            owned = set(result.scalars().all())
            for rank, names in rank_names.items():
                if names.issubset(owned):
                    return True
            return False
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
            from app.services.deck_service import deck_service
            if user.tickets <= 0:
                user.tickets = 1
            await deck_service.pull(session, user)

        await session.flush()


title_service = TitleService()
