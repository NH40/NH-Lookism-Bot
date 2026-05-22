import random
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.auction import AuctionLot
from app.constants.auction import AUCTION_TIERS, RANK_BY_TIER, FRAGMENT_TIERS


async def _generate_reward(tier: int) -> str:
    cfg = AUCTION_TIERS[tier]

    if cfg["reward_type"] == "tickets":
        amount = random.randint(2, 4) * max(1, tier)
        return json.dumps({"tickets": amount})

    elif cfg["reward_type"] == "potion":
        from app.data.shop import POTIONS
        potion = random.choice(POTIONS)
        return json.dumps({"potion_id": potion.potion_id, "name": potion.name})

    elif cfg["reward_type"] == "fragments":
        frag_types = FRAGMENT_TIERS.get(tier, ["ui_fragments"])
        frag_type = random.choice(frag_types)
        amount = random.randint(20, 50)
        labels = {
            "ui_fragments": "🔮 Фрагменты УИ",
            "alchemy_fragments": "🧪 Фрагменты алхимии",
            "path_fragments": "🔷 Фрагменты Пути",
        }
        return json.dumps({"frag_type": frag_type, "amount": amount, "label": labels.get(frag_type, frag_type)})

    elif cfg["reward_type"] == "absolute":
        from app.data.characters import CHARACTERS
        allowed = RANK_BY_TIER.get(tier, ["absolute"])
        candidates = [c for c in CHARACTERS if c["rank"] in allowed]
        if not candidates:
            candidates = [c for c in CHARACTERS if c["rank"] in ["gen_zero", "new_legend"]]
        char = random.choice(candidates)
        return json.dumps({
            "character": char["name"],
            "rank": char["rank"],
            "power": char["power"],
        })

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


async def _deliver_reward(
    session: AsyncSession, user: User, lot: AuctionLot
) -> None:
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
    elif lot.reward_type in ("character", "absolute"):
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
    elif lot.reward_type == "fragments":
        frag_type = data.get("frag_type", "ui_fragments")
        amount = data.get("amount", 10)
        current = getattr(user, frag_type, 0)
        setattr(user, frag_type, current + amount)
