import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.clan import Clan, ClanAuction
from app.services.clan.base import ClanBaseService


class ClanAuctionService(ClanBaseService):

    async def get_active_auction(self, session: AsyncSession, clan_id: int) -> ClanAuction | None:
        return await session.scalar(
            select(ClanAuction).where(ClanAuction.clan_id == clan_id, ClanAuction.is_finished == False)
        )

    async def bid_auction(self, session: AsyncSession, auction: ClanAuction, user: User, amount: int) -> dict:
        now = datetime.now(timezone.utc)
        ends_at = auction.ends_at
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        if now >= ends_at:
            return {"ok": False, "reason": "Аукцион завершён"}
        min_bid = auction.current_bid + max(1, int(auction.current_bid * 0.1)) if auction.current_bid > 0 else 1
        if amount < min_bid:
            return {"ok": False, "reason": f"Ставка должна быть минимум {min_bid:,} NHCoin"}
        if user.nh_coins < amount:
            return {"ok": False, "reason": "Недостаточно NHCoin"}
        if auction.leader_id and auction.leader_id != user.id:
            prev = await session.scalar(select(User).where(User.id == auction.leader_id))
            if prev:
                prev.nh_coins += auction.current_bid
        user.nh_coins -= amount
        auction.current_bid = amount
        auction.leader_id = user.id
        await session.flush()
        return {"ok": True}

    async def get_expired_auction_ids(self, session: AsyncSession) -> list[int]:
        """Возвращает IDs истёкших незавершённых аукционов."""
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(ClanAuction.id).where(ClanAuction.is_finished == False, ClanAuction.ends_at <= now)
        )
        return list(result.scalars().all())

    async def finish_auction_by_id(self, session: AsyncSession, auction_id: int) -> None:
        """Завершает один аукцион в уже открытой транзакции."""
        auction = await session.get(ClanAuction, auction_id)
        if not auction or auction.is_finished:
            return
        await self.give_auction_reward(session, auction)

    async def finish_expired_auctions(self, session: AsyncSession) -> None:
        import logging
        _log = logging.getLogger(__name__)
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(ClanAuction).where(ClanAuction.is_finished == False, ClanAuction.ends_at <= now)
        )
        auctions = result.scalars().all()
        for auction in auctions:
            # Пропускаем уже закрытые (могли быть закрыты предыдущей итерацией)
            if auction.is_finished:
                continue
            try:
                await self.give_auction_reward(session, auction)
            except Exception as e:
                _log.error(
                    f"give_auction_reward error for auction {auction.id}: {e}",
                    exc_info=True,
                )

    async def give_auction_reward(self, session: AsyncSession, auction: ClanAuction) -> None:
        if not auction.leader_id:
            auction.is_finished = True
            await session.flush()
            return
        winner = await session.scalar(select(User).where(User.id == auction.leader_id))
        if not winner:
            auction.is_finished = True
            await session.flush()
            return
        try:
            reward = json.loads(auction.reward_data) if auction.reward_data else {}
        except Exception:
            reward = {}

        rtype = reward.get("type")
        if rtype == "coins":
            winner.nh_coins += reward.get("amount", 0)
        elif rtype == "tickets":
            winner.tickets += reward.get("amount", 0)
        elif rtype == "path_fragments":
            winner.path_fragments = (winner.path_fragments or 0) + reward.get("amount", 0)
        elif rtype == "mastery_points":
            winner.mastery_points = (winner.mastery_points or 0) + reward.get("amount", 0)
        elif rtype == "ui_fragments":
            winner.ui_fragments = (winner.ui_fragments or 0) + reward.get("amount", 0)
        elif rtype == "potion":
            from app.services.potion_service import potion_service
            await potion_service.activate(session, winner, reward.get("potion_id"))
        elif rtype == "squad":
            from app.models.squad_member import SquadMember
            from app.data.squad import RANKS_BY_ID
            rank = reward.get("rank", "S")
            amount = reward.get("amount", 1)
            rank_cfg = RANKS_BY_ID.get(rank)
            for _ in range(amount):
                session.add(SquadMember(user_id=winner.id, rank=rank, base_power=rank_cfg.base_power if rank_cfg else 1000))
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, winner)
        elif rtype == "character":
            from app.data.characters import CHARACTERS
            pool = [c for c in CHARACTERS if c["rank"] == reward.get("rank", "king")]
            if pool:
                import random
                char = random.choice(pool)
                from app.models.character import UserCharacter
                session.add(UserCharacter(user_id=winner.id, character_id=char["name"], rank=char["rank"], power=char["power"]))

        auction.is_finished = True

        # Сначала сохраняем изменения в БД, потом уведомляем
        await session.flush()

        # Уведомляем победителя
        try:
            from app.bot_instance import get_bot
            bot = get_bot()
            if bot:
                label = reward.get("label", "Приз")
                await bot.send_message(
                    winner.tg_id,
                    f"🏆 <b>Вы победили в клановом аукционе!</b>\n\n🎁 {label}",
                    parse_mode="HTML",
                )
        except Exception:
            pass