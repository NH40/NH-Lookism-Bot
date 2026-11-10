"""Дань младших императоров (пользователь 2026-11-10).

Император лиги N получает `EMPIRE_TRIBUTE_PERCENT`% налога императоров той же страны в младших
лигах (у них не вычитается). Доля одного младшего делится между императорами каждой старшей
копии страны по числу их городов там. Потолок: за сутки (UTC) дань не больше
`EMPIRE_TRIBUTE_CAP_PERCENT`% собственного налога получателя за те же сутки — экономика не
должна разогнаться (выбор пользователя «10% + потолок 20%»).

Не в транзакции игрока: налог зачисляется при сборе дохода каждого игрока, и запись ещё в
строки старших императоров там дала бы взаимоблокировки (как при переносе стран). Фоновый
проход раз в `EMPIRE_TRIBUTE_SWEEP_SECONDS` берёт прирост `empire_collected` с прошлой отметки
(`tribute_mark`) — одной транзакцией, строки императоров по порядку id.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.country import base_code, league_of_code
from bot.config.empire import EMPIRE_TRIBUTE_CAP_PERCENT, EMPIRE_TRIBUTE_PERCENT
from bot.constant.ledger import REASON_EMPEROR_TRIBUTE
from bot.utils.log_context import coin_reason

log = logging.getLogger(__name__)

# Прирост налога с прошлой отметки; отметка двигается в том же запросе. Суточные счётчики
# обнуляются, когда сменился день. Только те, у кого есть города (иначе ни дани, ни налога).
_TAKE_SQL = text("""
WITH e AS (
    SELECT u.id, u.empire_collected - u.tribute_mark AS delta, u.empire_collected AS mark, u.country_code,
           (u.tribute_day IS DISTINCT FROM CAST(:today AS date)) AS new_day
    FROM users u
    WHERE EXISTS (SELECT 1 FROM cities c WHERE c.emperor_id = u.id)
    ORDER BY u.id
    FOR UPDATE OF u
)
UPDATE users u SET
    tribute_mark = e.mark,
    tribute_day = CAST(:today AS date),
    tribute_own = CASE WHEN e.new_day THEN 0 ELSE u.tribute_own END + GREATEST(e.delta, 0),
    tribute_got = CASE WHEN e.new_day THEN 0 ELSE u.tribute_got END
FROM e
WHERE u.id = e.id
RETURNING u.id, GREATEST(e.delta, 0), e.country_code, u.tribute_own, u.tribute_got
""")

_HOLDINGS_SQL = text(
    "SELECT country_code, emperor_id, count(*) FROM cities WHERE emperor_id IS NOT NULL GROUP BY 1, 2"
)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def plan(
    sources: list[tuple[int, int, str]],
    holdings: list[tuple[str, int, int]],
    room: dict[int, int],
) -> dict[int, int]:
    """Чистый расчёт: (император, прирост налога, его страна) → {получатель: дань}.
    `room` — сколько ещё можно получить за сутки (потолок). Без БД — проверяется отдельно."""
    copies: dict[tuple[str, int], list[tuple[int, int]]] = defaultdict(list)
    for code, emperor_id, cities in holdings:
        copies[(base_code(code), league_of_code(code))].append((emperor_id, cities))
    raw: dict[int, float] = defaultdict(float)
    for emperor_id, delta, code in sources:
        if delta <= 0 or not code:
            continue
        base, league = base_code(code), league_of_code(code)
        share = delta * EMPIRE_TRIBUTE_PERCENT / 100
        for (b, lg), holders in copies.items():
            if b != base or lg <= league:
                continue
            total = sum(c for _, c in holders)
            for receiver, cities in holders:
                if receiver != emperor_id:
                    raw[receiver] += share * cities / total
    return {r: min(int(v), max(0, room.get(r, 0))) for r, v in raw.items() if min(int(v), room.get(r, 0)) > 0}


async def run_once(session: AsyncSession) -> dict[int, int]:
    """Один проход. Коммитит. → {получатель: дань}."""
    rows = (await session.execute(_TAKE_SQL, {"today": _today()})).all()
    holdings = [tuple(r) for r in (await session.execute(_HOLDINGS_SQL)).all()]
    room = {uid: own * EMPIRE_TRIBUTE_CAP_PERCENT // 100 - got for uid, _, _, own, got in rows}
    paid = plan([(uid, delta, code) for uid, delta, code, _, _ in rows], holdings, room)
    with coin_reason(REASON_EMPEROR_TRIBUTE):
        for receiver in sorted(paid):
            await session.execute(
                text("UPDATE users SET nh_coins = nh_coins + :a, tribute_got = tribute_got + :a WHERE id = :u"),
                {"a": paid[receiver], "u": receiver},
            )
    await session.commit()
    return paid


async def sweep(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Фон: проход в своей сессии; сбой (например, взаимоблокировка с игроком) — отметка не
    сдвинулась, прирост посчитается в следующий раз."""
    async with session_factory() as session:
        paid = await run_once(session)
    return sum(paid.values())
