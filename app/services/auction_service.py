import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.auction import Auction, AuctionLot, AuctionBid
from app.models.user import User


AUCTION_ROUND_DURATION = 20  # минут на раунд

# Тиры аукциона: название, редкость, раунды, мин ставка
AUCTION_TIERS = {
    1: {"name": "Бронзовый",    "emoji": "🟫", "rounds": 2, "min_bid": 500,    "reward_type": "coins",     "color": "common"},
    2: {"name": "Серебряный",   "emoji": "⬜", "rounds": 2, "min_bid": 2000,   "reward_type": "potion",    "color": "uncommon"},
    3: {"name": "Золотой",      "emoji": "🟨", "rounds": 3, "min_bid": 5000,   "reward_type": "character", "color": "rare"},
    4: {"name": "Платиновый",   "emoji": "🟦", "rounds": 3, "min_bid": 15000,  "reward_type": "character", "color": "epic"},
    5: {"name": "Королевский",  "emoji": "🟧", "rounds": 4, "min_bid": 50000,  "reward_type": "character", "color": "legendary"},
}

RANK_BY_TIER = {
    3: ["king", "strong_king"],
    4: ["gen_zero", "new_legend"],
    5: ["legend", "peak", "absolute"],
}


class AuctionService:

    async def get_active_auction(
        self, session: AsyncSession
    ) -> Auction | None:
        result = await session.execute(
            select(Auction)
            .where(Auction.is_active == True)
            .order_by(Auction.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def start_new_auction(self, session: AsyncSession) -> Auction:
        tier = random.randint(1, 5)
        cfg = AUCTION_TIERS[tier]
        now = datetime.now(timezone.utc)

        auction = Auction(
            tier=tier,
            is_active=True,
            started_at=now,
            ends_at=now + timedelta(minutes=AUCTION_ROUND_DURATION),
        )
        session.add(auction)
        await session.flush()

        reward_data = await self._generate_reward(tier)
        lot = AuctionLot(
            auction_id=auction.id,
            reward_type=cfg["reward_type"],
            reward_data=reward_data,
            min_bid=cfg["min_bid"],
        )
        session.add(lot)
        await session.flush()
        return auction

    async def _generate_reward(self, tier: int) -> str:
        import json
        cfg = AUCTION_TIERS[tier]
        if cfg["reward_type"] == "coins":
            amount = random.randint(1000, 5000) * tier
            return json.dumps({"coins": amount})
        elif cfg["reward_type"] == "potion":
            from app.data.shop import POTIONS
            potion = random.choice(POTIONS)
            return json.dumps({"potion_id": potion.potion_id, "name": potion.name})
        else:
            from app.data.characters import CHARACTERS
            allowed = RANK_BY_TIER.get(tier, ["member"])
            candidates = [c for c in CHARACTERS if c["rank"] in allowed]
            char = random.choice(candidates) if candidates else random.choice(CHARACTERS)
            return json.dumps({
                "character": char["name"],
                "rank": char["rank"],
                "power": char["power"],
            })

    async def place_bid(
        self, session: AsyncSession, user: User, amount: int
    ) -> dict:
        auction = await self.get_active_auction(session)
        if not auction:
            return {"ok": False, "reason": "Нет активного аукциона"}

        now = datetime.now(timezone.utc)
        if now >= auction.ends_at:
            return {"ok": False, "reason": "Раунд завершён, ждите следующего"}

        lot_r = await session.execute(
            select(AuctionLot).where(AuctionLot.auction_id == auction.id)
        )
        lot = lot_r.scalar_one_or_none()
        if not lot:
            return {"ok": False, "reason": "Лот не найден"}

        min_bid = max(lot.min_bid, auction.final_bid + 1)
        if amount < min_bid:
            return {"ok": False, "reason": f"Минимальная ставка: {min_bid:,} NHCoin"}

        if user.nh_coins < amount:
            return {"ok": False, "reason": "Недостаточно NHCoin"}

        # Возврат денег предыдущему лидеру
        if auction.winner_id and auction.winner_id != user.id:
            prev_r = await session.execute(
                select(User).where(User.id == auction.winner_id)
            )
            prev_winner = prev_r.scalar_one_or_none()
            if prev_winner:
                prev_winner.nh_coins += auction.final_bid

        user.nh_coins -= amount
        auction.winner_id = user.id
        auction.final_bid = amount

        bid = AuctionBid(
            auction_id=auction.id,
            user_id=user.id,
            amount=amount,
        )
        session.add(bid)
        await session.flush()
        return {"ok": True, "bid": amount}

    async def finish_auction(self, session: AsyncSession) -> dict | None:
        auction = await self.get_active_auction(session)
        if not auction:
            return None

        now = datetime.now(timezone.utc)
        if now < auction.ends_at:
            return None

        cfg = AUCTION_TIERS.get(auction.tier, {})
        total_rounds = cfg.get("rounds", 2)

        # Считаем текущий раунд (по количеству завершённых)
        elapsed = (now - auction.started_at).total_seconds() / 60
        current_round = int(elapsed / AUCTION_ROUND_DURATION) + 1

        if current_round < total_rounds:
            # Продлеваем аукцион на следующий раунд
            auction.ends_at = auction.ends_at + timedelta(minutes=AUCTION_ROUND_DURATION)
            await session.flush()
            return {"continued": True, "round": current_round + 1, "total": total_rounds}

        # Финальный раунд — завершаем
        auction.is_active = False
        await session.flush()

        lot_r = await session.execute(
            select(AuctionLot).where(AuctionLot.auction_id == auction.id)
        )
        lot = lot_r.scalar_one_or_none()

        if auction.winner_id and lot:
            winner_r = await session.execute(
                select(User).where(User.id == auction.winner_id)
            )
            winner = winner_r.scalar_one_or_none()
            if winner:
                await self._deliver_reward(session, winner, lot)
                winner.auction_wins += 1
                await session.flush()

        return {
            "winner_id": auction.winner_id,
            "reward": lot.reward_data if lot else None,
            "tier": auction.tier,
        }

    async def _deliver_reward(
        self, session: AsyncSession, user: User, lot: AuctionLot
    ) -> None:
        import json
        data = json.loads(lot.reward_data)
        if lot.reward_type == "coins":
            user.nh_coins += data["coins"]
        elif lot.reward_type == "potion":
            from app.data.shop import POTION_MAP
            cfg = POTION_MAP.get(data["potion_id"])
            if cfg:
                from app.services.potion_service import potion_service
                await potion_service.apply_potion(
                    session, user.id,
                    cfg.effect_key, cfg.effect_value, cfg.duration_minutes
                )
        elif lot.reward_type == "character":
            from app.models.character import UserCharacter
            char = UserCharacter(
                user_id=user.id,
                character_id=data["character"],
                rank=data["rank"],
                power=data["power"],
            )
            session.add(char)
            await session.flush()
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, user)

    async def get_auction_display(
        self, session: AsyncSession, user: User
    ) -> dict:
        """Данные для отображения аукциона."""
        auction = await self.get_active_auction(session)
        if not auction:
            return {"active": False}

        import json
        now = datetime.now(timezone.utc)
        cfg = AUCTION_TIERS.get(auction.tier, {})
        total_rounds = cfg.get("rounds", 2)
        elapsed = (now - auction.started_at).total_seconds() / 60
        current_round = min(int(elapsed / AUCTION_ROUND_DURATION) + 1, total_rounds)
        remaining = max(0, int((auction.ends_at - now).total_seconds()))

        lot_r = await session.execute(
            select(AuctionLot).where(AuctionLot.auction_id == auction.id)
        )
        lot = lot_r.scalar_one_or_none()

        # Лидер
        leader_name = "Ставок нет"
        if auction.winner_id:
            leader_r = await session.execute(
                select(User).where(User.id == auction.winner_id)
            )
            leader = leader_r.scalar_one_or_none()
            if leader:
                leader_name = leader.full_name

        # Количество ставок
        bids_count_r = await session.execute(
            select(AuctionBid).where(AuctionBid.auction_id == auction.id)
        )
        bids_count = len(bids_count_r.scalars().all())

        # Лот
        reward_str = "Неизвестно"
        if lot:
            try:
                data = json.loads(lot.reward_data)
                if lot.reward_type == "coins":
                    reward_str = f"💰 {data['coins']:,} NHCoin"
                elif lot.reward_type == "potion":
                    reward_str = f"🧪 {data.get('name', 'Зелье')}"
                elif lot.reward_type == "character":
                    from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI
                    rank = data.get("rank", "")
                    emoji = RANK_EMOJI.get(rank, "❓")
                    cfg2 = RANK_CONFIG_MAP.get(rank)
                    label = cfg2.label if cfg2 else rank
                    reward_str = f"{emoji} {data['character']} [{label}] — {data['power']:,} мощи"
            except Exception:
                pass

        min_next = max(lot.min_bid if lot else 0, auction.final_bid + 1)

        return {
            "active": True,
            "auction": auction,
            "tier": auction.tier,
            "tier_name": cfg.get("name", ""),
            "tier_emoji": cfg.get("emoji", "🏛"),
            "current_round": current_round,
            "total_rounds": total_rounds,
            "remaining": remaining,
            "reward_str": reward_str,
            "current_bid": auction.final_bid,
            "min_next_bid": min_next,
            "leader_name": leader_name,
            "bids_count": bids_count,
            "is_leader": auction.winner_id == user.id,
            "lot": lot,
        }


auction_service = AuctionService()