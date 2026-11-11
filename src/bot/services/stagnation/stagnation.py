"""Застой кругов — кого предупредить (пользователь 2026-11-12). Сам штраф к доходу —
`services/business.stagnating` (при сборе и на экране кошелька)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.game import STAGNATION_HOURS
from bot.constant.ledger import BATTLE_BOTS, BATTLE_CITY, BATTLE_PVP, BATTLE_THRONE

_KINDS = (BATTLE_BOTS, BATTLE_CITY, BATTLE_PVP, BATTLE_THRONE)
_FIND_SQL = text("""
SELECT u.id FROM users u
WHERE u.phase = 'circle'
  AND u.last_active_at > now() - interval '7 days'
  AND EXISTS (SELECT 1 FROM districts d JOIN cities c ON c.id = d.city_id
              WHERE c.country_code = u.country_code AND d.owner_id IS NULL)
  AND NOT EXISTS (SELECT 1 FROM battle_log b WHERE b.attacker_id = u.id AND b.kind = ANY(:kinds)
                  AND b.created_at > now() - make_interval(hours => :h))
""")


async def find_stagnating(session_factory: async_sessionmaker[AsyncSession]) -> list[int]:
    """Круги в застое, заходившие за неделю (остальным пуш ни к чему)."""
    async with session_factory() as session:
        return list((await session.execute(_FIND_SQL, {"kinds": list(_KINDS), "h": STAGNATION_HOURS})).scalars())
