"""Сила развития (СР) — по стоимости прокачки в рублях (пользователь 2026-11-24, переработка СР от 2026-11-20).

Единица — рубль: где у системы есть реальная цена, берётся она (чёрный рынок — техники, пути, гениальности по
уровням, второе тело; донат-уровни клана), остальное оценено в том же масштабе (числа — `config/top`, живая
настройка). NHCoin-вложения клана (земли, здания) переводятся по курсу `SR_NHCOIN_PER_RUB`.

СР игрока — вся его прокачка. СР клана — сумма СР участников, заходивших за `SR_CLAN_ACTIVE_DAYS` дней, плюс
развитие самого клана: донат-уровни, земли, здания. Один запрос на всех игроков (правило 3).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _cumulative(unlock: int, levels: dict[int, int], top: int = 10) -> list[int]:
    """[стоимость при уровне 1, 2, …, top] — открытие + уровни до текущего включительно."""
    out, total = [], unlock
    for level in range(1, top + 1):
        if level > 1:
            total += levels.get(level, 0)
        out.append(total)
    return out


def _params() -> dict:
    from bot.config import top as cfg
    from bot.config.donate import (
        GENIUS_LEVEL_PRICES, GENIUS_UNLOCK, PATH_LEVEL_PRICES, PATH_UNLOCK, SECOND_BODY_PRICE, TECHNIQUE_LEVEL_PRICES,
        TECHNIQUE_UNLOCK,
    )
    from bot.constant.absolute import ABSOLUTES

    t = cfg.top
    return {
        "abs": list(ABSOLUTES),
        "tech": _cumulative(TECHNIQUE_UNLOCK, TECHNIQUE_LEVEL_PRICES), "path": _cumulative(PATH_UNLOCK, PATH_LEVEL_PRICES),
        "gen": _cumulative(GENIUS_UNLOCK, GENIUS_LEVEL_PRICES), "body": SECOND_BODY_PRICE,
        "stat": t.SR_STAT_RANK, "mastery": t.SR_MASTERY_LEVEL, "awakening": t.SR_AWAKENING_LEVEL, "mt": t.SR_MASTERY_TECH_TIER,
        "absolute": t.SR_ABSOLUTE, "school": t.SR_SCHOOL, "monster": t.SR_MONSTER, "business": t.SR_BUSINESS_LEVEL,
    }


# Родословная — по лестнице пути (оценка, пользователь 2026-11-24).
_PLAYER_SQL = """
WITH t AS (SELECT user_id, sum((CAST(:tech AS int[]))[least(greatest(level, 1), 10)]) s FROM user_techniques GROUP BY 1),
     p AS (SELECT user_id, sum((CAST(:path AS int[]))[least(greatest(level, 1), 10)]) s FROM user_paths GROUP BY 1),
     g AS (SELECT user_id, sum((CAST(:gen AS int[]))[least(greatest(level, 1), 10)]) s FROM user_geniuses GROUP BY 1),
     mt AS (SELECT user_id, :mt * sum(tier) s FROM mastery_techniques GROUP BY 1),
     sc AS (SELECT user_id, :school * count(*) s FROM user_schools WHERE owned GROUP BY 1),
     ab AS (SELECT user_id, :absolute * count(DISTINCT card_code) s FROM card_stacks WHERE quantity > 0 AND card_code = ANY(:abs) GROUP BY 1)
SELECT u.id,
       :stat * (u.stat_strength + u.stat_speed + u.stat_endurance + u.stat_agility)
     + :mastery * (u.mastery_strength + u.mastery_speed + u.mastery_endurance + u.mastery_technique)
     + CASE WHEN u.bloodline IS NOT NULL THEN (CAST(:path AS int[]))[least(greatest(u.bloodline_level, 1), 10)] ELSE 0 END
     + CASE WHEN u.bloodline2 IS NOT NULL THEN (CAST(:path AS int[]))[least(greatest(u.bloodline2_level, 1), 10)] ELSE 0 END
     + :awakening * u.awakening_level + CASE WHEN u.second_body THEN :body ELSE 0 END
     + CASE WHEN u.monster_potential THEN :monster ELSE 0 END + :business * (u.business_level + u.business_capacity)
     + coalesce(t.s, 0) + coalesce(p.s, 0) + coalesce(g.s, 0) + coalesce(mt.s, 0) + coalesce(sc.s, 0) + coalesce(ab.s, 0) AS score
FROM users u
LEFT JOIN t ON t.user_id = u.id LEFT JOIN p ON p.user_id = u.id LEFT JOIN g ON g.user_id = u.id
LEFT JOIN mt ON mt.user_id = u.id LEFT JOIN sc ON sc.user_id = u.id LEFT JOIN ab ON ab.user_id = u.id
"""


async def player_scores(session: AsyncSession, user_ids: list[int] | None = None) -> dict[int, int]:
    sql = _PLAYER_SQL + (" WHERE u.id = ANY(:ids)" if user_ids else "")
    params = _params()
    if user_ids:
        params["ids"] = user_ids
    return {int(uid): int(s or 0) for uid, s in (await session.execute(text(sql), params)).all()}


async def clan_scores(session: AsyncSession) -> dict[int, int]:
    """СР клана = сумма СР активных участников + донат-уровни (₽) + земли и здания (NHCoin по курсу)."""
    from bot.config import top as cfg
    from bot.config.clan import CLAN_BUILDINGS, CLAN_DONATE_BASE_PRICE, CLAN_DONATE_PRICE_STEP, CLAN_LAND_PRICE_STEP, CLAN_START_LANDS

    t = cfg.top
    params = _params() | {
        "days": int(t.SR_CLAN_ACTIVE_DAYS), "dbase": CLAN_DONATE_BASE_PRICE, "dstep": CLAN_DONATE_PRICE_STEP,
        "land": CLAN_LAND_PRICE_STEP, "start": CLAN_START_LANDS, "rate": max(1, int(t.SR_NHCOIN_PER_RUB)),
        "kinds": list(CLAN_BUILDINGS), "bases": [CLAN_BUILDINGS[k][1] for k in CLAN_BUILDINGS],
    }
    rows = (await session.execute(text(
        f"""WITH ps AS ({_PLAYER_SQL}),
            members AS (
              SELECT m.clan_id, sum(ps.score) s FROM clan_members m JOIN ps ON ps.id = m.user_id
              JOIN users u ON u.id = m.user_id WHERE u.last_active_at > now() - make_interval(days => :days) GROUP BY 1),
            prices AS (SELECT * FROM unnest(CAST(:kinds AS varchar[]), CAST(:bases AS bigint[])) AS x(kind, base)),
            buildings AS (
              SELECT b.clan_id, sum(p.base * b.count * (b.count + 1) / 2) s FROM clan_buildings b JOIN prices p ON p.kind = b.kind GROUP BY 1)
            SELECT c.id,
                   coalesce(members.s, 0)
                 + c.donate_level * :dbase + :dstep * c.donate_level * (c.donate_level - 1) / 2
                 + (:land * greatest(c.lands - :start, 0) * (greatest(c.lands - :start, 0) + 1) / 2 + coalesce(buildings.s, 0)) / :rate
            FROM clans c LEFT JOIN members ON members.clan_id = c.id LEFT JOIN buildings ON buildings.clan_id = c.id"""),
        params)).all()
    return {int(c): int(s or 0) for c, s in rows}
