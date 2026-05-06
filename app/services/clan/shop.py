import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanMember
from app.constants.clan import CLAN_SHOP_MAP, CLAN_AUCTION_REWARDS, CLAN_UPGRADES_MAP
from app.services.clan.base import ClanBaseService


class ClanShopService(ClanBaseService):

    async def buy_clan_shop(self, session: AsyncSession, clan: Clan, buyer: User, item_id: str) -> dict:
        item = CLAN_SHOP_MAP.get(item_id)
        if not item:
            return {"ok": False, "reason": "Товар не найден"}
        if clan.treasury < item.price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {item.price:,})"}

        clan.treasury -= item.price
        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        users = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()

        if item.item_type == "tickets":
            for u in users:
                u.tickets += item.value

        elif item.item_type == "potion":
            from app.services.potion_service import potion_service
            for u in users:
                await potion_service.activate(session, u, item.value)

        elif item.item_type == "squad":
            val = item.value
            from app.models.squad_member import SquadMember
            from app.data.squad import RANKS_BY_ID
            rank_cfg = RANKS_BY_ID.get(val["rank"])
            for u in users:
                for _ in range(val["amount"]):
                    session.add(SquadMember(user_id=u.id, rank=val["rank"], base_power=rank_cfg.base_power if rank_cfg else 1000))
            from app.repositories.squad_repo import squad_repo
            for u in users:
                await squad_repo.update_user_combat_power(session, u)
            await self.recalc_power(session, clan)

        elif item.item_type == "character":
            from app.data.characters import CHARACTERS
            pool = [c for c in CHARACTERS if c["rank"] == item.value] or [c for c in CHARACTERS if c["rank"] == "member"]
            from app.models.character import UserCharacter
            for u in users:
                char = random.choice(pool)
                session.add(UserCharacter(user_id=u.id, character_id=char["name"], rank=char["rank"], power=char["power"]))

        elif item.item_type == "auction":
            from app.services.clan.auction import ClanAuctionService as CAS
            from datetime import datetime, timezone, timedelta
            from app.models.clan import ClanAuction
            import json
            rewards = CLAN_AUCTION_REWARDS.get(item.value, CLAN_AUCTION_REWARDS["common"])
            reward = random.choice(rewards)
            auction = ClanAuction(
                clan_id=clan.id, reward_type=item.value,
                reward_data=json.dumps(reward),
                ends_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(auction)

        await session.flush()

        # Уведомляем всех участников
        await self._notify_shop_purchase(clan, buyer, item, users)

        return {"ok": True, "item": item}

    async def _notify_shop_purchase(self, clan, buyer, item, users) -> None:
        try:
            from app.bot_instance import get_bot
            bot = get_bot()
            if not bot:
                return
            for u in users:
                if u.id == buyer.id:
                    continue
                try:
                    await bot.send_message(
                        u.tg_id,
                        f"🛒 <b>Покупка в магазине клана!</b>\n\n"
                        f"🏯 Клан: {clan.name}\n"
                        f"👤 Куплено: {buyer.full_name}\n"
                        f"🎁 {item.name}\n"
                        f"💰 Потрачено из казны: {item.price:,} NHCoin",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        except Exception:
            pass

    async def buy_upgrade(self, session: AsyncSession, clan: Clan, user: User, upgrade_id: str) -> dict:
        upgrade = CLAN_UPGRADES_MAP.get(upgrade_id)
        if not upgrade:
            return {"ok": False, "reason": "Улучшение не найдено"}
        if clan.treasury < upgrade.price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {upgrade.price:,})"}

        if upgrade.upgrade_type == "slots":
            if clan.bonus_max_members + upgrade.value > upgrade.max_total:
                return {"ok": False, "reason": f"Лимит +{upgrade.max_total} мест"}
            clan.bonus_max_members += upgrade.value
            clan.max_members = 5 + clan.bonus_max_members
        elif upgrade.upgrade_type == "income":
            if clan.bonus_income_pct > 0:
                return {"ok": False, "reason": "Уже куплено"}
            clan.bonus_income_pct += upgrade.value
        elif upgrade.upgrade_type == "ticket":
            if clan.bonus_ticket_pct > 0:
                return {"ok": False, "reason": "Уже куплено"}
            clan.bonus_ticket_pct += upgrade.value
        elif upgrade.upgrade_type == "train":
            if clan.bonus_train_pct > 0:
                return {"ok": False, "reason": "Уже куплено"}
            clan.bonus_train_pct += upgrade.value

        clan.treasury -= upgrade.price
        await self._apply_clan_bonuses(session, clan)
        await session.flush()
        return {"ok": True, "upgrade": upgrade}