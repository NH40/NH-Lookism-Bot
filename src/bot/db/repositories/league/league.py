"""Лиги (репозиторий). Ничего не коммитит — коммитит сервис."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.league import (
    SCORE_AWAKENING,
    SCORE_BLOODLINE_LEVEL,
    SCORE_DONATE_LOG,
    SCORE_GENIUS_LEVEL,
    SCORE_MASTERY,
    SCORE_PATH_LEVEL,
    SCORE_POTENTIAL,
    SCORE_POWER_LOG,
    SCORE_SECOND_BODY,
    SCORE_STAT_RANK,
    SCORE_TECHNIQUE_LEVEL,
)
from bot.constant.characteristic import POTENTIAL_ORDER


async def all_scores(session: AsyncSession) -> list[tuple[int, int, int]]:
    """(игрок, текущая лига, счёт) всех игроков одним запросом (правило 3)."""
    rows = await session.execute(text("""
        WITH pay AS (SELECT user_id, SUM(amount_rub) AS rub FROM payments GROUP BY 1),
             old AS (SELECT tg_id AS user_id, total AS rub FROM lbp1_donations),
             tech AS (SELECT user_id, SUM(level) AS lv FROM user_techniques GROUP BY 1),
             gen AS (SELECT user_id, SUM(level) AS lv FROM user_geniuses GROUP BY 1),
             pth AS (SELECT user_id, SUM(level) AS lv FROM user_paths GROUP BY 1)
        SELECT u.id, u.league, round(
              :power * log(greatest(u.army_power_cache, 0) + 1)
            + :donate * log(coalesce(pay.rub, 0) + coalesce(old.rub, 0) + 1)
            + :stat * (u.stat_strength + u.stat_speed + u.stat_endurance + u.stat_agility)
            + :mastery * (u.mastery_strength + u.mastery_speed + u.mastery_endurance + u.mastery_technique)
            + :awakening * u.awakening_level
            + :potential * coalesce(array_position(CAST(:order AS varchar[]), u.potential), 1)
            + :bloodline * (u.bloodline_level + u.bloodline2_level)
            + :body * (CASE WHEN u.second_body THEN 1 ELSE 0 END)
            + :tech * coalesce(tech.lv, 0) + :gen * coalesce(gen.lv, 0) + :path * coalesce(pth.lv, 0)
        )::int
        FROM users u
        LEFT JOIN pay ON pay.user_id = u.id LEFT JOIN old ON old.user_id = u.id LEFT JOIN tech ON tech.user_id = u.id
        LEFT JOIN gen ON gen.user_id = u.id LEFT JOIN pth ON pth.user_id = u.id
    """), {
        "power": SCORE_POWER_LOG, "donate": SCORE_DONATE_LOG, "stat": SCORE_STAT_RANK, "mastery": SCORE_MASTERY, "awakening": SCORE_AWAKENING,
        "potential": SCORE_POTENTIAL, "order": list(POTENTIAL_ORDER), "bloodline": SCORE_BLOODLINE_LEVEL, "body": SCORE_SECOND_BODY,
        "tech": SCORE_TECHNIQUE_LEVEL, "gen": SCORE_GENIUS_LEVEL, "path": SCORE_PATH_LEVEL,
    })
    return [(int(a), int(b), int(c)) for a, b, c in rows.all()]


async def set_scores(session: AsyncSession, values: list[tuple[int, int]]) -> None:
    if values:
        await session.execute(text("UPDATE users SET league_score = :s WHERE id = :u"), [{"u": u, "s": s} for u, s in values])


async def set_leagues(session: AsyncSession, values: list[tuple[int, int]]) -> None:
    if values:
        await session.execute(text("UPDATE users SET league = :l WHERE id = :u"), [{"u": u, "l": l} for u, l in values])


_MOVE = (
    # Вызовы висят на районах старой карты, войны между разными лигами больше невозможны.
    "UPDATE district_challenges SET status = :cancelled, resolution = :admin, resolved_at = now() WHERE status = :pending",
    """UPDATE emperor_wars w SET status = :war_cancelled, resolution = :admin, resolved_at = now()
       FROM users a, users d WHERE w.status = :war_pending AND a.id = w.attacker_id AND d.id = w.defender_id AND a.league <> d.league""",
    """CREATE TEMP TABLE _cmap ON COMMIT DROP AS
       SELECT b.id AS old_id, n.id AS new_id, right(n.country_code, 1)::int AS lg, n.country_code AS new_code
       FROM cities b JOIN cities n ON n.name = b.name AND left(n.country_code, 2) = b.country_code AND length(n.country_code) = 3
       WHERE length(b.country_code) = 2""",
    # Здания — раньше владельцев: нужны старые владельцы районов.
    """UPDATE businesses b SET district_id = n.id
       FROM districts o JOIN _cmap m ON m.old_id = o.city_id JOIN users u ON u.id = o.owner_id AND u.league = m.lg
       JOIN districts n ON n.city_id = m.new_id AND n.number = o.number
       WHERE b.district_id = o.id""",
    """UPDATE businesses b SET origin_city_id = m.new_id FROM users u, _cmap m
       WHERE b.holder_id = u.id AND b.origin_city_id = m.old_id AND m.lg = u.league""",
    """UPDATE districts n SET owner_id = o.owner_id, captured_at = o.captured_at
       FROM districts o JOIN _cmap m ON m.old_id = o.city_id JOIN users u ON u.id = o.owner_id AND u.league = m.lg
       WHERE n.city_id = m.new_id AND n.number = o.number""",
    """UPDATE districts o SET owner_id = NULL, captured_at = NULL
       FROM users u, cities c WHERE u.id = o.owner_id AND u.league > 0 AND c.id = o.city_id AND length(c.country_code) = 2""",
    """UPDATE cities n SET emperor_id = o.emperor_id
       FROM cities o JOIN _cmap m ON m.old_id = o.id JOIN users u ON u.id = o.emperor_id AND u.league = m.lg WHERE n.id = m.new_id""",
    """UPDATE cities o SET emperor_id = NULL FROM users u WHERE u.id = o.emperor_id AND u.league > 0 AND length(o.country_code) = 2""",
    """UPDATE users u SET city_id = m.new_id, country_code = m.new_code FROM _cmap m WHERE u.city_id = m.old_id AND m.lg = u.league""",
    """DELETE FROM emperor_tax_overrides t USING users e, users p WHERE e.id = t.emperor_id AND p.id = t.user_id AND e.league <> p.league""",
)


async def move_to_league_maps(session: AsyncSession, params: dict) -> None:
    """Запуск лиг: районы, здания, города и троны едут вместе с владельцем на копию карты его лиги."""
    for sql in _MOVE:
        await session.execute(text(sql), {k: v for k, v in params.items() if f":{k}" in sql})


async def strip_territory(session: AsyncSession, user_id: int, params: dict) -> None:
    """Повышение: всё на карте теряется, как при выселении, только здания сгорают. Доход начислен до этого."""
    for sql, keys in (
        ("UPDATE emperor_wars SET status = :war_cancelled, resolution = :admin, resolved_at = now() WHERE status = :war_pending AND (attacker_id = :uid OR defender_id = :uid)", ("war_cancelled", "admin", "war_pending", "uid")),
        ("DELETE FROM businesses WHERE holder_id = :uid", ("uid",)),
        ("UPDATE cities SET emperor_id = NULL WHERE emperor_id = :uid", ("uid",)),
        ("DELETE FROM emperor_tax_overrides WHERE emperor_id = :uid OR user_id = :uid", ("uid",)),
    ):
        await session.execute(text(sql), {k: params[k] for k in keys})
