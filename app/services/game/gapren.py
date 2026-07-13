from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.gapren import GaprenChallenge
from app.config.game_balance import (
    GAPREN_WINS_NEEDED,
    GAPREN_FIGHT2_POWER_PCT,
    GAPREN_FIGHT3_POWER_PCT,
    GAPREN_COOLDOWN_HOURS,
)
from app.services.combat_service import fight_district


def gapren_power(user: User, streak: int) -> int:
    """Сила Гапрёна на следующий бой по текущей серии побед подряд."""
    if streak <= 0:
        return user.emperor_entry_power or user.combat_power
    pct = GAPREN_FIGHT2_POWER_PCT if streak == 1 else GAPREN_FIGHT3_POWER_PCT
    return int(user.combat_power * (1 + pct / 100))


async def get_or_create_challenge(session: AsyncSession, user_id: int) -> GaprenChallenge:
    challenge = await session.scalar(
        select(GaprenChallenge).where(GaprenChallenge.user_id == user_id)
    )
    if not challenge:
        challenge = GaprenChallenge(user_id=user_id, streak=0)
        session.add(challenge)
        await session.flush()
    return challenge


async def attack_gapren(session: AsyncSession, user: User) -> dict:
    if user.phase != "emperor":
        return {"ok": False, "reason": "Только для фазы Императора"}

    challenge = await get_or_create_challenge(session, user.id)

    now = datetime.now(timezone.utc)
    if challenge.cooldown_until and challenge.cooldown_until > now:
        secs = int((challenge.cooldown_until - now).total_seconds())
        return {"ok": False, "reason": "На перезарядке", "cd": secs}

    if challenge.streak >= GAPREN_WINS_NEEDED:
        return {"ok": False, "reason": "Гапрён уже трижды повержен — пробуждение открыто!"}

    opponent_power = gapren_power(user, challenge.streak)
    fight = await fight_district(session, user, opponent_power)

    if fight["win"]:
        challenge.streak = min(GAPREN_WINS_NEEDED, challenge.streak + 1)
    else:
        challenge.streak = 0
    challenge.cooldown_until = now + timedelta(hours=GAPREN_COOLDOWN_HOURS)
    await session.flush()

    return {
        "ok": True,
        "win": fight["win"],
        "is_crit": fight["is_crit"],
        "user_power": fight["user_power"],
        "opponent_power": opponent_power,
        "streak": challenge.streak,
        "unlocked": challenge.streak >= GAPREN_WINS_NEEDED,
    }
