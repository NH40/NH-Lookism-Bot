from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.clan import Clan
from app.constants.clan import CLAN_UPGRADES_MAP
from app.services.clan.base import ClanBaseService


class ClanUpgradesService(ClanBaseService):

    async def buy_upgrade(
        self, session: AsyncSession, clan: Clan, user: User, upgrade_id: str
    ) -> dict:
        upgrade = CLAN_UPGRADES_MAP.get(upgrade_id)
        if not upgrade:
            return {"ok": False, "reason": "Улучшение не найдено"}
        if clan.treasury < upgrade.price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {upgrade.price:,})"}

        # Проверяем лимиты
        if upgrade.upgrade_type == "slots":
            if clan.bonus_max_members + upgrade.value > upgrade.max_total:
                remaining = upgrade.max_total - clan.bonus_max_members
                if remaining <= 0:
                    return {"ok": False, "reason": f"Достигнут максимум +{upgrade.max_total} мест"}
                return {"ok": False, "reason": f"Можно добавить ещё максимум {remaining} мест"}
            clan.bonus_max_members += upgrade.value
            clan.max_members = 5 + clan.bonus_max_members

        elif upgrade.upgrade_type == "income":
            if clan.bonus_income_pct > 0:
                return {"ok": False, "reason": "Бонус к доходу уже куплен"}
            clan.bonus_income_pct += upgrade.value

        elif upgrade.upgrade_type == "ticket":
            if clan.bonus_ticket_pct > 0:
                return {"ok": False, "reason": "Бонус к тикету уже куплен"}
            clan.bonus_ticket_pct += upgrade.value

        elif upgrade.upgrade_type == "train":
            if clan.bonus_train_pct > 0:
                return {"ok": False, "reason": "Бонус к тренировкам уже куплен"}
            clan.bonus_train_pct += upgrade.value

        clan.treasury -= upgrade.price

        # Применяем бонусы всем участникам клана
        await self._apply_clan_bonuses(session, clan)

        # Уведомляем всех участников
        await self._notify_upgrade(clan, user, upgrade)

        await session.flush()
        return {"ok": True, "upgrade": upgrade}

    async def _notify_upgrade(self, clan: Clan, buyer: "User", upgrade) -> None:
        try:
            from app.bot_instance import get_bot
            from sqlalchemy import select
            from app.models.clan import ClanMember
            from app.models.user import User as UserModel
            from app.database import AsyncSessionFactory

            bot = get_bot()
            if not bot:
                return

            async with AsyncSessionFactory() as session:
                members_r = await session.execute(
                    select(ClanMember).where(ClanMember.clan_id == clan.id)
                )
                for m in members_r.scalars().all():
                    if m.user_id == buyer.id:
                        continue
                    u = await session.scalar(select(UserModel).where(UserModel.id == m.user_id))
                    if u:
                        try:
                            await bot.send_message(
                                u.tg_id,
                                f"⚙️ <b>Улучшение клана куплено!</b>\n\n"
                                f"🏯 Клан: {clan.name}\n"
                                f"👤 Куплено: {buyer.full_name}\n"
                                f"✨ {upgrade.name}\n"
                                f"📝 {upgrade.desc}",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
        except Exception:
            pass