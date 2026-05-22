"""
Логика дуэлей карточек:
  - vs бот (3 тира: gen2 / gen1 / gen0)
  - vs игрок (PvP через Redis-вызов)
"""
import json
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.character import UserCharacter
from app.models.card_deck import UserDeck
from app.services.cooldown_service import cooldown_service
from app.data.characters import CHARACTERS
from app.constants.cards import LEVEL_MULTIPLIERS, BOT_TIERS, DUEL_BOT_CD_BASE

CHALLENGE_TTL = 90  # секунд на принятие PvP-вызова


# ── Хелперы ──────────────────────────────────────────────────────────────────

def effective_power(uc: UserCharacter) -> int:
    return int(uc.base_power * LEVEL_MULTIPLIERS.get(uc.level, 1.0))


def team_power(cards: list[UserCharacter]) -> int:
    return sum(effective_power(c) for c in cards)


async def build_user_team(session: AsyncSession, user_id: int) -> list[UserCharacter]:
    """5 карточек из активной колоды + до 5 случайных из остатка (без N+1)."""
    deck_rows = (await session.execute(
        select(UserDeck).where(UserDeck.user_id == user_id).order_by(UserDeck.slot)
    )).scalars().all()
    deck_char_ids = {d.char_id for d in deck_rows}

    # Batch-load deck chars in one query
    deck_chars: list[UserCharacter] = []
    if deck_char_ids:
        deck_chars = list((await session.execute(
            select(UserCharacter).where(UserCharacter.id.in_(deck_char_ids))
        )).scalars().all())

    # Random 5 from the rest — ORDER BY RANDOM() in SQL, no Python sampling
    bench_filters = [UserCharacter.user_id == user_id]
    if deck_char_ids:
        bench_filters.append(UserCharacter.id.notin_(deck_char_ids))
    picks: list[UserCharacter] = list((await session.execute(
        select(UserCharacter).where(*bench_filters).order_by(func.random()).limit(5)
    )).scalars().all())

    return deck_chars + picks


# Pre-compute bot pools per tier at module load (not on every duel call)
_BOT_POOLS: dict[str, list[dict]] = {
    tier_id: ([c for c in CHARACTERS if c["rank"] in cfg["allowed_ranks"]] or list(CHARACTERS))
    for tier_id, cfg in BOT_TIERS.items()
}


def _gen_bot_team(tier: str) -> list[tuple[str, int, int]]:
    """Возвращает [(name, base_power, level), ...] для команды бота."""
    cfg = BOT_TIERS.get(tier, BOT_TIERS["gen2"])
    pool = _BOT_POOLS.get(tier, list(CHARACTERS))
    picks = random.choices(pool, k=5)
    levels = random.choices([0, 1, 2, 3], weights=cfg["level_weights"], k=5)
    return [(p["name"], p["power"], lvl) for p, lvl in zip(picks, levels)]


def bot_team_power_val(bot_cards: list[tuple[str, int, int]]) -> int:
    return sum(int(bp * LEVEL_MULTIPLIERS.get(lvl, 1.0)) for _, bp, lvl in bot_cards)


# ── Сервис ───────────────────────────────────────────────────────────────────

class DuelService:

    async def duel_vs_bot(self, session: AsyncSession, user: User, tier: str) -> dict:
        cd_key = cooldown_service.duel_bot_key(user.id)
        if await cooldown_service.is_on_cooldown(cd_key):
            ttl = await cooldown_service.get_ttl(cd_key)
            return {"ok": False, "reason": f"КД дуэли: {cooldown_service.format_ttl(ttl)}"}

        user_team = await build_user_team(session, user.id)
        if not user_team:
            return {"ok": False, "reason": "У тебя нет карточек для дуэли!"}

        bot_cards = _gen_bot_team(tier)
        u_power = team_power(user_team)
        b_power = bot_team_power_val(bot_cards)
        won = u_power >= b_power

        # КД с учётом мастерства скорости + донат-бонуса
        from app.models.skill import UserMastery
        mastery = await session.scalar(
            select(UserMastery).where(UserMastery.user_id == user.id)
        )
        speed_levels = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
        raw_speed = speed_levels.get(mastery.speed if mastery else 0, 0)
        speed_pct = int(raw_speed * getattr(user, "skill_path_bonus_multiplier", 1.0))
        donat_pct = 20 if getattr(user, "donat_duel_cd", False) else 0
        cd_seconds = cooldown_service.apply_speed_reduction(
            DUEL_BOT_CD_BASE, speed_pct, extra_pct=donat_pct
        )
        await cooldown_service.set_cooldown(cd_key, cd_seconds)

        tier_cfg = BOT_TIERS.get(tier, BOT_TIERS["gen2"])
        dust_reward = 0
        if won:
            dust_reward = random.randint(tier_cfg["dust_min"], tier_cfg["dust_max"])
            user.card_dust = getattr(user, "card_dust", 0) + dust_reward
            await session.flush()

        return {
            "ok": True, "won": won,
            "user_power": u_power, "bot_power": b_power,
            "user_team": user_team, "bot_cards": bot_cards,
            "dust_reward": dust_reward,
            "tier_name": tier_cfg["name"], "tier_emoji": tier_cfg["emoji"],
            "cd_seconds": cd_seconds,
            "speed_pct": speed_pct,
            "donat_pct": donat_pct,
        }

    async def send_challenge(
        self, session: AsyncSession, from_user: User, to_user: User
    ) -> dict:
        if from_user.id == to_user.id:
            return {"ok": False, "reason": "Нельзя вызвать самого себя"}

        has_cards = await session.scalar(
            select(UserCharacter.id).where(UserCharacter.user_id == from_user.id).limit(1)
        )
        if not has_cards:
            return {"ok": False, "reason": "У тебя нет карточек для дуэли!"}

        key = cooldown_service.duel_challenge_key(to_user.id)
        if await cooldown_service.redis.exists(key):
            return {"ok": False, "reason": "Этот игрок уже получил вызов, подожди."}

        payload = json.dumps({
            "from_user_id": from_user.id,
            "from_tg_id": from_user.tg_id,
            "from_name": from_user.full_name,
        })
        await cooldown_service.redis.setex(key, CHALLENGE_TTL, payload)
        return {"ok": True, "ttl": CHALLENGE_TTL}

    async def accept_challenge(self, session: AsyncSession, to_user: User) -> dict:
        key = cooldown_service.duel_challenge_key(to_user.id)
        raw = await cooldown_service.redis.get(key)
        if not raw:
            return {"ok": False, "reason": "Вызов истёк или уже был принят"}

        data = json.loads(raw)
        await cooldown_service.redis.delete(key)

        from_user = await session.get(User, data["from_user_id"])
        if not from_user:
            return {"ok": False, "reason": "Инициатор дуэли не найден"}

        team_a = await build_user_team(session, from_user.id)
        team_b = await build_user_team(session, to_user.id)

        if not team_a:
            return {"ok": False, "reason": "У бросившего вызов нет карточек"}
        if not team_b:
            return {"ok": False, "reason": "У тебя нет карточек для дуэли!"}

        power_a = team_power(team_a)
        power_b = team_power(team_b)
        a_won = power_a >= power_b
        winner = from_user if a_won else to_user

        dust_reward = random.randint(50, 120)
        winner.card_dust = getattr(winner, "card_dust", 0) + dust_reward
        await session.flush()

        return {
            "ok": True,
            "from_user": from_user, "to_user": to_user,
            "power_a": power_a, "power_b": power_b,
            "winner": winner,
            "dust_reward": dust_reward,
        }

    async def decline_challenge(self, to_user: User) -> bool:
        key = cooldown_service.duel_challenge_key(to_user.id)
        return bool(await cooldown_service.redis.delete(key))


duel_service = DuelService()
