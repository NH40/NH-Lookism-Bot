"""Сила развития (СР) — топ кланов по прокачке игроков, а не по сырой мощи (пользователь 2026-11-20).

Считается ВСЯ прокачка игрока (то, что не покупается армией и деньгами):
  характеристики — 1 очко за каждую ступень ранга каждой из 4;
  мастерство — 5 за уровень каждого из 4; техники мастерства — 10 за каждую изученную;
  техники — 5 за каждую изученную + 3 за каждый её уровень; пути — так же; гениальности — так же;
  родословные — 10 за каждую + 4 за уровень; пробуждение — 25 за уровень; второе тело — 30; монстр-потенциал — 30;
  абсолюты — 20 за каждую карту; учителя статистов (школы) — 5 за каждого; прокачка бизнеса — 1 за уровень.
Сила клана — среднее СР топ-`CLAN_DEV_TOP` участников: твинки не раздувают, один кит не вытягивает.
Один запрос на всех игроков (правило 3).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CLAN_DEV_TOP = 10

_PLAYER_SQL = """
WITH t AS (SELECT user_id, sum(5 + 3 * level) s FROM user_techniques GROUP BY 1),
     p AS (SELECT user_id, sum(5 + 3 * level) s FROM user_paths GROUP BY 1),
     g AS (SELECT user_id, sum(5 + 3 * level) s FROM user_geniuses GROUP BY 1),
     mt AS (SELECT user_id, 10 * count(*) s FROM mastery_techniques GROUP BY 1),
     sc AS (SELECT user_id, 5 * count(*) s FROM user_schools WHERE owned GROUP BY 1),
     ab AS (SELECT user_id, 20 * count(DISTINCT card_code) s FROM card_stacks WHERE quantity > 0 AND card_code = ANY(:abs) GROUP BY 1)
SELECT u.id,
       (u.stat_strength + u.stat_speed + u.stat_endurance + u.stat_agility)
     + 5 * (u.mastery_strength + u.mastery_speed + u.mastery_endurance + u.mastery_technique)
     + CASE WHEN u.bloodline IS NOT NULL THEN 10 + 4 * u.bloodline_level ELSE 0 END
     + CASE WHEN u.bloodline2 IS NOT NULL THEN 10 + 4 * u.bloodline2_level ELSE 0 END
     + 25 * u.awakening_level + CASE WHEN u.second_body THEN 30 ELSE 0 END + CASE WHEN u.monster_potential THEN 30 ELSE 0 END
     + u.business_level + u.business_capacity
     + coalesce(t.s, 0) + coalesce(p.s, 0) + coalesce(g.s, 0) + coalesce(mt.s, 0) + coalesce(sc.s, 0) + coalesce(ab.s, 0) AS score
FROM users u
LEFT JOIN t ON t.user_id = u.id LEFT JOIN p ON p.user_id = u.id LEFT JOIN g ON g.user_id = u.id
LEFT JOIN mt ON mt.user_id = u.id LEFT JOIN sc ON sc.user_id = u.id LEFT JOIN ab ON ab.user_id = u.id
"""


async def player_scores(session: AsyncSession, user_ids: list[int] | None = None) -> dict[int, int]:
    from bot.constant.absolute import ABSOLUTES

    sql = _PLAYER_SQL + (" WHERE u.id = ANY(:ids)" if user_ids else "")
    params: dict = {"abs": list(ABSOLUTES)}
    if user_ids:
        params["ids"] = user_ids
    return {int(uid): int(s or 0) for uid, s in (await session.execute(text(sql), params)).all()}


async def clan_scores(session: AsyncSession) -> dict[int, int]:
    """СР клана = среднее СР его топ-10 участников."""
    from bot.constant.absolute import ABSOLUTES

    rows = (await session.execute(text(
        f"""WITH ps AS ({_PLAYER_SQL}), ranked AS (
              SELECT m.clan_id, ps.score, row_number() OVER (PARTITION BY m.clan_id ORDER BY ps.score DESC) rn
              FROM clan_members m JOIN ps ON ps.id = m.user_id)
            SELECT clan_id, round(avg(score)) FROM ranked WHERE rn <= :top GROUP BY clan_id"""),
        {"abs": list(ABSOLUTES), "top": CLAN_DEV_TOP})).all()
    return {int(c): int(s or 0) for c, s in rows}
