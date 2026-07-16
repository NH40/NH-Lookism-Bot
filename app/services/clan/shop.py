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
        discount_pct = await self.get_shop_discount_pct(session, clan.id)
        price = int(item.price * (1 - discount_pct / 100))
        if clan.treasury < price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {price:,})"}

        if item.item_type == "auction":
            existing = await self.get_active_auction(session, clan.id)
            if existing:
                return {"ok": False, "reason": "В клане уже идёт аукцион"}

        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        users = (await session.execute(
            select(User).where(User.id.in_(user_ids)).order_by(User.id)
        )).scalars().all()

        if item.item_type == "tickets":
            from app.config.game_balance import ticket_hard_cap
            for u in users:
                u.tickets = min(u.tickets + item.value, ticket_hard_cap(u))

        elif item.item_type == "potion":
            from app.services.potion_service import potion_service
            for u in users:
                await potion_service.activate(session, u, item.value)

        elif item.item_type == "squad":
            val = item.value
            from app.data.squad import RANKS_BY_ID
            from app.repositories.squad_repo import squad_repo
            rank_cfg = RANKS_BY_ID.get(val["rank"])
            base_power = rank_cfg.base_power if rank_cfg else 1000
            for u in users:
                await squad_repo.add_count(session, u.id, val["rank"], 0, val["amount"], base_power=base_power)
                await squad_repo.update_user_combat_power(session, u)
            await self.recalc_power(session, clan)

        elif item.item_type == "character":
            from app.data.characters import CHARACTERS
            pool = [c for c in CHARACTERS if c["rank"] == item.value] or [c for c in CHARACTERS if c["rank"] == "member"]
            from app.models.character import UserCharacter
            for u in users:
                char = random.choice(pool)
                session.add(UserCharacter(user_id=u.id, character_id=char["name"], rank=char["rank"], base_power=char["power"], power=char["power"]))

        elif item.item_type == "auction":
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

        # Казну списываем ПОСЛЕ всех per-user операций (squad_repo.update_user_combat_power
        # трогает users, затем clan) — иначе списание тут заранее лочит clan и при
        # конкурентной операции, которая лочит users->clan в этом порядке (например,
        # emperor.py при дропе карты), возникает deadlock (users->clan vs clan->users).
        clan.treasury -= price
        await session.flush()

        import asyncio
        tg_ids = [u.tg_id for u in users if u.id != buyer.id]
        clan_name = clan.name
        buyer_name = buyer.full_name
        asyncio.create_task(self._notify_shop_purchase(clan_name, buyer_name, item, price, tg_ids))

        return {"ok": True, "item": item, "price": price}

    async def _notify_shop_purchase(self, clan_name: str, buyer_name: str, item, price: int, tg_ids: list) -> None:
        try:
            from app.bot_instance import get_bot
            import asyncio
            bot = get_bot()
            if not bot:
                return
            text = (
                f"🛒 <b>Покупка в магазине клана!</b>\n\n"
                f"🏯 Клан: {clan_name}\n"
                f"👤 Куплено: {buyer_name}\n"
                f"🎁 {item.name}\n"
                f"💰 Потрачено из казны: {price:,} NHCoin"
            )
            for tg_id in tg_ids:
                try:
                    await bot.send_message(tg_id, text, parse_mode="HTML")
                except Exception:
                    pass
        except Exception:
            pass

    async def buy_upgrade(self, session: AsyncSession, clan: Clan, user: User, upgrade_id: str) -> dict:
        upgrade = CLAN_UPGRADES_MAP.get(upgrade_id)
        if not upgrade:
            return {"ok": False, "reason": "Улучшение не найдено"}
        discount_pct = await self.get_shop_discount_pct(session, clan.id)
        price = int(upgrade.price * (1 - discount_pct / 100))
        if clan.treasury < price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {price:,})"}

        new_bonus_max_members = new_max_members = None
        new_bonus_income_pct = new_bonus_ticket_pct = new_bonus_train_pct = None

        if upgrade.upgrade_type == "slots":
            if clan.bonus_max_members + upgrade.value > upgrade.max_total:
                return {"ok": False, "reason": f"Лимит +{upgrade.max_total} мест"}
            new_bonus_max_members = clan.bonus_max_members + upgrade.value
            new_max_members = 5 + new_bonus_max_members
        elif upgrade.upgrade_type == "income":
            if clan.bonus_income_pct > 0:
                return {"ok": False, "reason": "Уже куплено"}
            new_bonus_income_pct = clan.bonus_income_pct + upgrade.value
        elif upgrade.upgrade_type == "ticket":
            if clan.bonus_ticket_pct > 0:
                return {"ok": False, "reason": "Уже куплено"}
            new_bonus_ticket_pct = clan.bonus_ticket_pct + upgrade.value
        elif upgrade.upgrade_type == "train":
            if clan.bonus_train_pct > 0:
                return {"ok": False, "reason": "Уже куплено"}
            new_bonus_train_pct = clan.bonus_train_pct + upgrade.value

        # Сначала применяем бонусы к users (передавая ещё не сохранённые новые
        # значения через override-параметры), и только потом мутируем сам clan —
        # порядок блокировок users->clan, единообразно со squad_repo и emperor.py
        # (иначе deadlock с конкурентными операциями по тем же двум строкам).
        await self._apply_clan_bonuses(
            session, clan,
            bonus_income_pct=new_bonus_income_pct,
            bonus_ticket_pct=new_bonus_ticket_pct,
            bonus_train_pct=new_bonus_train_pct,
        )

        if new_bonus_max_members is not None:
            clan.bonus_max_members = new_bonus_max_members
            clan.max_members = new_max_members
        if new_bonus_income_pct is not None:
            clan.bonus_income_pct = new_bonus_income_pct
        if new_bonus_ticket_pct is not None:
            clan.bonus_ticket_pct = new_bonus_ticket_pct
        if new_bonus_train_pct is not None:
            clan.bonus_train_pct = new_bonus_train_pct
        clan.treasury -= price

        await session.flush()
        return {"ok": True, "upgrade": upgrade, "price": price}