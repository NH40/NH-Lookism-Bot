"""API-роутер Mini App: бой с боссом на карте (`services.district.fight_boss`).

Список боссов отдаёт `GET /api/map` (поле `events`) — здесь только сам бой.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers._common import plain_lines
from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, cooldown_text, require_user
from bot.services.district import (
    BattleOnCooldownError,
    BossAlreadyDefeatedError,
    EventGoneError,
    NoAttackersError,
    fight_boss,
)
from bot.texts.district import NO_ATTACKERS
from bot.texts.event import BOSS_ALREADY_DEFEATED_ALERT, BOSS_NAMES, EVENT_GONE_ALERT, FRAGMENT_NAMES

router = APIRouter(prefix="/api/boss", tags=["boss"])


class BossFightOut(BaseModel):
    message: str
    won: bool
    boss: str
    boss_name: str
    rounds: int
    attacker_power: int
    attacker_dead: int
    boss_power: int
    boss_remaining_power: int
    fragments: int
    fragment_name: str
    journal: list[str] = []


@router.post("/{event_id}/fight", response_model=BossFightOut)
async def fight(
    event_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> BossFightOut:
    user = await require_user(session, user_id)
    try:
        result = await fight_boss(session, redis, user, event_id)
    except EventGoneError:
        raise bad(EVENT_GONE_ALERT)
    except BossAlreadyDefeatedError:
        raise bad(BOSS_ALREADY_DEFEATED_ALERT)
    except NoAttackersError:
        raise bad(NO_ATTACKERS)
    except BattleOnCooldownError as exc:
        raise bad(cooldown_text("Сражение", exc.retry_after_seconds))

    name = BOSS_NAMES.get(result.boss, result.boss)
    fragment_name = FRAGMENT_NAMES[result.fragment_kind]
    if result.won:
        message = f"Победа над боссом {name}! +{result.fragments} {fragment_name}."
    else:
        message = f"Босс {name} оказался сильнее. Можно попробовать снова после КД."
    return BossFightOut(
        message=message, won=result.won, boss=result.boss, boss_name=name, rounds=result.rounds,
        attacker_power=result.attacker_power, attacker_dead=result.attacker_dead,
        boss_power=result.boss_power, boss_remaining_power=result.boss_remaining_power,
        fragments=result.fragments, fragment_name=fragment_name, journal=plain_lines(result.journal),
    )
