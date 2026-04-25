import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.auction import Auction, AuctionLot, AuctionBid
from app.models.user import User

AUCTION_ROUND_SECONDS = 90
BID_EXTEND_SECONDS = 15
NEXT_AUCTION_KEY = "next_auction_at"

TIER_WEIGHTS = {
    1: 50,
    2: 30,
    3: 15,
    4: 4,
    5: 1,
}

AUCTION_TIERS = {
    1: {"name": "Бронзовый",   "emoji": "🟫", "rounds": 2, "min_bid": 500,   "reward_type": "tickets"},
    2: {"name": "Серебряный",  "emoji": "⬜", "rounds": 2, "min_bid": 2000,  "reward_type": "potion"},
    3: {"name": "Золотой",     "emoji": "🟨", "rounds": 3, "min_bid": 5000,  "reward_type": "character"},
    4: {"name": "Платиновый",  "emoji": "🟦", "rounds": 3, "min_bid": 15000, "reward_type": "character"},
    5: {"name": "Королевский", "emoji": "🟧", "rounds": 4, "min_bid": 50000, "reward_type": "character"},
}

RANK_BY_TIER = {
    3: ["king", "strong_king"],
    4: ["gen_zero", "new_legend"],
    5: ["gen_zero", "new_legend"],
}

AUCTION_PAUSE_MIN = 10
AUCTION_PAUSE_MAX = 20


def _get_random_tier() -> int:
    tiers = list(TIER_WEIGHTS.keys())
    weights = list(TIER_WEIGHTS.values())
    return random.choices(tiers, weights=weights, k=1)[0]


class AuctionService:

    async def get_active_auction(self, session: AsyncSession) -> Auction | None:
        result = await session.execute(
            select(Auction)
            .where(Auction.is_active == True)
            .order_by(Auction.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_auction_time(self, session: AsyncSession) -> datetime | None:
        """
        Берём TTL из Redis — время устанавливается один раз при завершении
        аукциона, не пересчитывается каждый раз.
        """
        from app.services.cooldown_service import cooldown_service
        ttl = await cooldown_service.get_ttl(NEXT_AUCTION_KEY)
        if ttl <= 0:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=ttl)

    async def _set_next_auction_pause(self) -> int:
        """Устанавливает случайную паузу до следующего аукциона в Redis."""
        from app.services.cooldown_service import cooldown_service
        pause = random.randint(AUCTION_PAUSE_MIN, AUCTION_PAUSE_MAX) * 60
        await cooldown_service.set_cooldown(NEXT_AUCTION_KEY, pause)
        return pause

    async def start_new_auction(self, session: AsyncSession) -> Auction | None:
        """Запускает новый аукцион если пауза прошла."""
        from app.services.cooldown_service import cooldown_service

        # Если КД ещё не истёк — рано
        if await cooldown_service.is_on_cooldown(NEXT_AUCTION_KEY):
            return None

        tier = _get_random_tier()
        cfg = AUCTION_TIERS[tier]
        now = datetime.now(timezone.utc)

        auction = Auction(
            tier=tier,
            is_active=True,
            current_round=1,
            started_at=now,
            ends_at=now + timedelta(seconds=AUCTION_ROUND_SECONDS),
            final_bid=0,
            winner_id=None,
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

        if cfg["reward_type"] == "tickets":
            amount = random.randint(1, 3) * tier
            return json.dumps({"tickets": amount})

        elif cfg["reward_type"] == "potion":
            from app.data.shop import POTIONS
            potion = random.choice(POTIONS)
            return json.dumps({"potion_id": potion.potion_id, "name": potion.name})

        else:
            from app.data.characters import CHARACTERS
            allowed = RANK_BY_TIER.get(tier, ["member", "boss", "king"])
            candidates = [c for c in CHARACTERS if c["rank"] in allowed]
            if not candidates:
                candidates = [c for c in CHARACTERS if c["rank"] in ["king", "strong_king"]]
            char = random.choice(candidates)
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
            return {"ok": False, "reason": "Раунд завершён"}

        lot_r = await session.execute(
            select(AuctionLot)
            .where(AuctionLot.auction_id == auction.id)
            .order_by(AuctionLot.id.desc())
            .limit(1)
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
            prev = prev_r.scalar_one_or_none()
            if prev:
                prev.nh_coins += auction.final_bid

        user.nh_coins -= amount
        auction.winner_id = user.id
        auction.final_bid = amount

        remaining = (auction.ends_at - now).total_seconds()
        if remaining < BID_EXTEND_SECONDS:
            auction.ends_at = now + timedelta(seconds=BID_EXTEND_SECONDS)

        session.add(AuctionBid(
            auction_id=auction.id,
            user_id=user.id,
            amount=amount,
        ))
        await session.flush()
        return {
            "ok": True,
            "bid": amount,
            "new_ends_at": auction.ends_at,
        }

    async def tick(self, session: AsyncSession) -> dict | None:
        auction = await self.get_active_auction(session)
        if not auction:
            return None

        now = datetime.now(timezone.utc)
        if now < auction.ends_at:
            return None

        cfg = AUCTION_TIERS.get(auction.tier, {})
        total_rounds = cfg.get("rounds", 2)
        current_round = auction.current_round or 1

        lot_r = await session.execute(
            select(AuctionLot)
            .where(AuctionLot.auction_id == auction.id)
            .order_by(AuctionLot.id.desc())
            .limit(1)
        )
        lot = lot_r.scalar_one_or_none()

        winner_info = None
        if auction.winner_id:
            winner_r = await session.execute(
                select(User).where(User.id == auction.winner_id)
            )
            winner = winner_r.scalar_one_or_none()
            if winner:
                winner_info = {
                    "id": winner.id,
                    "tg_id": winner.tg_id,
                    "name": winner.full_name,
                    "bid": auction.final_bid,
                    "notifications": winner.notifications_enabled,
                }
                if lot:
                    await self._deliver_reward(session, winner, lot)
                    winner.auction_wins += 1

        if current_round >= total_rounds:
            # Финал — завершаем и устанавливаем паузу
            auction.is_active = False
            await session.flush()

            # Устанавливаем случайную паузу ОДИН РАЗ в Redis
            pause_sec = await self._set_next_auction_pause()
            pause_min = pause_sec // 60

            return {
                "event": "auction_end",
                "tier": auction.tier,
                "tier_name": cfg.get("name", ""),
                "tier_emoji": cfg.get("emoji", "🏛"),
                "round": current_round,
                "total_rounds": total_rounds,
                "winner": winner_info,
                "lot": lot,
                "next_in_minutes": pause_min,
            }
        else:
            # Следующий раунд
            auction.current_round = current_round + 1
            auction.final_bid = 0
            auction.winner_id = None
            auction.ends_at = now + timedelta(seconds=AUCTION_ROUND_SECONDS)

            new_reward = await self._generate_reward(auction.tier)
            new_lot = AuctionLot(
                auction_id=auction.id,
                reward_type=cfg["reward_type"],
                reward_data=new_reward,
                min_bid=cfg.get("min_bid", 500),
            )
            session.add(new_lot)
            await session.flush()

            return {
                "event": "round_end",
                "tier": auction.tier,
                "tier_name": cfg.get("name", ""),
                "tier_emoji": cfg.get("emoji", "🏛"),
                "round": current_round,
                "total_rounds": total_rounds,
                "next_round": current_round + 1,
                "winner": winner_info,
                "lot": lot,
            }

    async def _deliver_reward(
        self, session: AsyncSession, user: User, lot: AuctionLot
    ) -> None:
        import json
        data = json.loads(lot.reward_data)
        if lot.reward_type == "tickets":
            user.tickets += data["tickets"]
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

    async def get_display_data(
        self, session: AsyncSession, user: User
    ) -> dict:
        auction = await self.get_active_auction(session)
        if not auction:
            next_time = await self.get_next_auction_time(session)
            now = datetime.now(timezone.utc)
            wait_seconds = 0
            if next_time and next_time > now:
                wait_seconds = int((next_time - now).total_seconds())
            return {"active": False, "wait_seconds": wait_seconds}

        import json
        now = datetime.now(timezone.utc)
        cfg = AUCTION_TIERS.get(auction.tier, {})
        total_rounds = cfg.get("rounds", 2)
        current_round = auction.current_round or 1
        remaining = max(0, int((auction.ends_at - now).total_seconds()))

        lot_r = await session.execute(
            select(AuctionLot)
            .where(AuctionLot.auction_id == auction.id)
            .order_by(AuctionLot.id.desc())
            .limit(1)
        )
        lot = lot_r.scalar_one_or_none()

        leader_name = "Ставок нет"
        is_leader = False
        if auction.winner_id:
            leader_r = await session.execute(
                select(User).where(User.id == auction.winner_id)
            )
            leader = leader_r.scalar_one_or_none()
            if leader:
                leader_name = leader.full_name
                is_leader = leader.id == user.id

        bids_r = await session.execute(
            select(AuctionBid).where(AuctionBid.auction_id == auction.id)
        )
        bids_count = len(bids_r.scalars().all())

        reward_str = "Неизвестно"
        if lot:
            try:
                data = json.loads(lot.reward_data)
                if lot.reward_type == "tickets":
                    reward_str = f"🎟 {data['tickets']} тикетов"
                elif lot.reward_type == "potion":
                    reward_str = f"🧪 {data.get('name', 'Зелье')}"
                elif lot.reward_type == "character":
                    from app.data.characters import RANK_EMOJI, RANK_CONFIG_MAP
                    rank = data.get("rank", "")
                    emoji = RANK_EMOJI.get(rank, "❓")
                    rc = RANK_CONFIG_MAP.get(rank)
                    label = rc.label if rc else rank
                    reward_str = (
                        f"{emoji} {data['character']} "
                        f"[{label}] {data['power']:,} мощи"
                    )
            except Exception:
                pass

        min_next = max(lot.min_bid if lot else 0, auction.final_bid + 1)
        cur = auction.final_bid
        bid_5  = max(min_next, int(cur * 1.05)) if cur > 0 else min_next
        bid_10 = max(min_next, int(cur * 1.10)) if cur > 0 else int(min_next * 1.1)
        bid_50 = max(min_next, int(cur * 1.50)) if cur > 0 else int(min_next * 1.5)

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
            "current_bid": cur,
            "min_next_bid": min_next,
            "bid_5": bid_5,
            "bid_10": bid_10,
            "bid_50": bid_50,
            "leader_name": leader_name,
            "is_leader": is_leader,
            "bids_count": bids_count,
        }


auction_service = AuctionService()