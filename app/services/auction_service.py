import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.auction import Auction, AuctionLot, AuctionBid
from app.models.user import User


AUCTION_DURATION_MINUTES = 30
TIER_CONFIGS = {
    1: {"min_bid": 500,    "reward_type": "coins",     "reward_range": (1000, 5000)},
    2: {"min_bid": 2000,   "reward_type": "potion",    "reward_range": None},
    3: {"min_bid": 5000,   "reward_type": "character", "reward_range": None},
    4: {"min_bid": 15000,  "reward_type": "character", "reward_range": None},
    5: {"min_bid": 50000,  "reward_type": "character", "reward_range": None},
}


class AuctionService:

    async def get_active_auction(
        self, session: AsyncSession
    ) -> Auction | None:
        result = await session.execute(
            select(Auction).where(Auction.is_active == True)
            .order_by(Auction.started_at.desc())
        )
        return result.scalar_one_or_none()

    async def start_new_auction(self, session: AsyncSession) -> Auction:
        tier = random.randint(1, 5)
        now = datetime.now(timezone.utc)
        auction = Auction(
            tier=tier,
            is_active=True,
            started_at=now,
            ends_at=now + timedelta(minutes=AUCTION_DURATION_MINUTES),
        )
        session.add(auction)
        await session.flush()

        # Создаём лот
        cfg = TIER_CONFIGS[tier]
        reward_data = await self._generate_reward(tier, cfg)
        lot = AuctionLot(
            auction_id=auction.id,
            reward_type=cfg["reward_type"],
            reward_data=reward_data,
            min_bid=cfg["min_bid"],
        )
        session.add(lot)
        await session.flush()
        return auction

    async def _generate_reward(self, tier: int, cfg: dict) -> str:
        import json
        if cfg["reward_type"] == "coins":
            amount = random.randint(*cfg["reward_range"])
            return json.dumps({"coins": amount})
        elif cfg["reward_type"] == "potion":
            from app.data.shop import POTIONS
            potion = random.choice(POTIONS)
            return json.dumps({"potion_id": potion.potion_id, "name": potion.name})
        else:
            # character
            from app.data.characters import CHARACTERS, RANK_CONFIG_MAP
            rank_by_tier = {3: ["king","strong_king"], 4: ["gen_zero","new_legend"], 5: ["legend","peak","absolute"]}
            allowed_ranks = rank_by_tier.get(tier, ["member"])
            candidates = [c for c in CHARACTERS if c["rank"] in allowed_ranks]
            char = random.choice(candidates) if candidates else random.choice(CHARACTERS)
            return json.dumps({"character": char["name"], "rank": char["rank"], "power": char["power"]})

    async def place_bid(
        self, session: AsyncSession, user: User, amount: int
    ) -> dict:
        auction = await self.get_active_auction(session)
        if not auction:
            return {"ok": False, "reason": "Нет активного аукциона"}

        now = datetime.now(timezone.utc)
        if now >= auction.ends_at:
            return {"ok": False, "reason": "Аукцион завершён"}

        lot_result = await session.execute(
            select(AuctionLot).where(AuctionLot.auction_id == auction.id)
        )
        lot = lot_result.scalar_one_or_none()
        if not lot:
            return {"ok": False, "reason": "Лот не найден"}

        min_bid = max(lot.min_bid, auction.final_bid + 1)
        if amount < min_bid:
            return {"ok": False, "reason": f"Минимальная ставка: {min_bid:,}"}

        if user.nh_coins < amount:
            return {"ok": False, "reason": "Недостаточно NHCoin"}

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

        auction.is_active = False
        await session.flush()

        if not auction.winner_id:
            return {"winner_id": None, "reward": None}

        # Выдаём награду победителю
        from app.models.user import User as UserModel
        result = await session.execute(
            select(UserModel).where(UserModel.id == auction.winner_id)
        )
        winner = result.scalar_one_or_none()
        if winner:
            lot_r = await session.execute(
                select(AuctionLot).where(AuctionLot.auction_id == auction.id)
            )
            lot = lot_r.scalar_one_or_none()
            if lot:
                await self._deliver_reward(session, winner, lot)
                winner.auction_wins += 1

        await session.flush()
        return {"winner_id": auction.winner_id, "reward": lot.reward_data if lot else None}

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


auction_service = AuctionService()