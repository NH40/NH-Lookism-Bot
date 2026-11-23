"""Переезд при переходе в другую лигу (пользователь 2026-11-23): «что-то среднее» между «всё сгорает» и «всё едет».

- Район на карте новой лиги (тот же город, тот же номер) свободен — переезжает вместе со зданиями.
- Занят другим игроком — заявка (`league_claims`): здания отложены, 24 часа на бесплатный вызов на этот район.
  Победа — район и здания (сколько влезет, остаток — NHCoin); проигрыш или истёк срок — здания возвращаются NHCoin.
- В новой лиге нет такого города — здания возвращаются NHCoin.
- Трон: свободен в новой лиге — едет с игроком, занят — снимается (дальше бой по кнопке «👑 Бой за трон»);
  не осталось городов — император становится кругом.
- Висящие вызовы и войны с участием игрока отменяются: он ушёл с этой карты.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import league_of_code
from bot.config.game import BUSINESS_BUILD_COST
from bot.constant.admin.world import RESOLUTION_ADMIN, WAR_CANCELLED
from bot.constant.empire import WAR_PENDING
from bot.constant.league import CLAIM_EXPIRED, CLAIM_LOST, CLAIM_OPEN, CLAIM_WON
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST

CLAIM_HOURS = 24


@dataclass(slots=True)
class MoveReport:
    moved: int = 0  # районов переехало
    claims: list[tuple[int, int, str]] = field(default_factory=list)  # (заявка, номер района, город)
    refunded: int = 0  # NHCoin за здания, которым некуда ехать
    thrones_moved: int = 0
    thrones_lost: int = 0
    city_kept: bool = False  # живёт в том же городе новой лиги (страну выбирать не нужно)


def refund_for(buildings: dict[str, int]) -> int:
    return sum(BUSINESS_BUILD_COST.get(t, 0) * int(n) for t, n in buildings.items())


async def _counterpart(session: AsyncSession, city_id: int, league: int) -> int | None:
    """Тот же город на карте лиги `league` (копия страны с кодом лиги)."""
    rows = (await session.execute(text(
        "SELECT n.id, n.country_code FROM cities o JOIN cities n ON n.name = o.name AND left(n.country_code, 2) = left(o.country_code, 2) "
        "WHERE o.id = :c"
    ), {"c": city_id})).all()
    return next((int(cid) for cid, code in rows if league_of_code(code) == league), None)


async def _buildings_on(session: AsyncSession, district_id: int) -> dict[str, int]:
    rows = (await session.execute(text("SELECT type, count(*) FROM businesses WHERE district_id = :d GROUP BY 1"), {"d": district_id})).all()
    return {str(t): int(n) for t, n in rows}


async def move_on_promotion(session: AsyncSession, user_id: int, league: int) -> MoveReport:
    """Перевести территорию игрока на карту лиги `league`. НЕ коммитит (часть `promote`)."""
    rep = MoveReport()
    now = datetime.now(timezone.utc)
    await session.execute(text(
        "UPDATE emperor_wars SET status = :c, resolution = :a, resolved_at = now() WHERE status = :p AND (attacker_id = :u OR defender_id = :u)"
    ), {"c": WAR_CANCELLED, "a": RESOLUTION_ADMIN, "p": WAR_PENDING, "u": user_id})
    owned = (await session.execute(text(
        "SELECT id, city_id, number, captured_at FROM districts WHERE owner_id = :u ORDER BY id FOR UPDATE"
    ), {"u": user_id})).all()
    for did, city_id, number, captured in owned:
        target_city = await _counterpart(session, int(city_id), league)
        target = (await session.execute(text(
            "SELECT id, owner_id FROM districts WHERE city_id = :c AND number = :n FOR UPDATE"
        ), {"c": target_city, "n": number})).first() if target_city else None
        buildings = await _buildings_on(session, did)
        await session.execute(text("UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE id = :d"), {"d": did})
        if target is not None and target[1] is None:  # свободен — едет со зданиями
            await session.execute(text("DELETE FROM businesses WHERE district_id = :n"), {"n": target[0]})  # сироты на ничейном районе
            await session.execute(text("UPDATE businesses SET district_id = :n WHERE district_id = :o"), {"n": target[0], "o": did})
            await session.execute(text("UPDATE districts SET owner_id = :u, captured_at = :t WHERE id = :n"),
                                  {"u": user_id, "t": captured or now, "n": target[0]})
            rep.moved += 1
            continue
        await session.execute(text("DELETE FROM businesses WHERE district_id = :d"), {"d": did})
        if target is not None:  # занят другим игроком — заявка на 24 часа, здания отложены
            claim_id = await session.scalar(text(
                "INSERT INTO league_claims (user_id, district_id, buildings, status, expires_at) "
                "VALUES (:u, :d, CAST(:b AS jsonb), :s, :e) RETURNING id"
            ), {"u": user_id, "d": target[0], "b": _json(buildings), "s": CLAIM_OPEN, "e": now + timedelta(hours=CLAIM_HOURS)})
            name = await session.scalar(text("SELECT name FROM cities WHERE id = :c"), {"c": target_city})
            rep.claims.append((int(claim_id), int(number), str(name)))
        else:  # такого города в лиге нет — здания деньгами
            rep.refunded += refund_for(buildings)
    await session.execute(text("DELETE FROM emperor_tax_overrides WHERE user_id = :u"), {"u": user_id})  # ставки императора прошлой лиги
    # --- троны и владения
    for cid, in (await session.execute(text("SELECT id FROM cities WHERE emperor_id = :u FOR UPDATE"), {"u": user_id})).all():
        target_city = await _counterpart(session, int(cid), league)
        await session.execute(text("UPDATE cities SET emperor_id = NULL WHERE id = :c"), {"c": cid})
        free = target_city is not None and await session.scalar(text("SELECT emperor_id IS NULL FROM cities WHERE id = :c FOR UPDATE"), {"c": target_city})
        if free:
            await session.execute(text("UPDATE cities SET emperor_id = :u WHERE id = :c"), {"u": user_id, "c": target_city})
            await session.execute(text("UPDATE businesses SET origin_city_id = :n WHERE holder_id = :u AND origin_city_id = :o"),
                                  {"n": target_city, "u": user_id, "o": cid})
            rep.thrones_moved += 1
        else:
            await session.execute(text("DELETE FROM businesses WHERE holder_id = :u AND origin_city_id = :o AND district_id IS NULL"),
                                  {"u": user_id, "o": cid})
            rep.thrones_lost += 1
    if not await session.scalar(text("SELECT 1 FROM cities WHERE emperor_id = :u LIMIT 1"), {"u": user_id}):
        await session.execute(text("DELETE FROM businesses WHERE holder_id = :u AND district_id IS NULL"), {"u": user_id})
        await session.execute(text("DELETE FROM emperor_tax_overrides WHERE emperor_id = :u"), {"u": user_id})
        await session.execute(text("UPDATE users SET phase = :c WHERE id = :u AND phase = :f"), {"c": PHASE_CIRCLE, "f": PHASE_FIST, "u": user_id})
    # --- место жительства
    city_id = await session.scalar(text("SELECT city_id FROM users WHERE id = :u"), {"u": user_id})
    new_city = await _counterpart(session, int(city_id), league) if city_id else None
    code = await session.scalar(text("SELECT country_code FROM cities WHERE id = :c"), {"c": new_city}) if new_city else None
    await session.execute(text("UPDATE users SET league = :l, city_id = :c, country_code = :k WHERE id = :u"),
                          {"l": league, "c": new_city, "k": code, "u": user_id})
    rep.city_kept = new_city is not None
    if rep.refunded:
        await session.execute(text("UPDATE users SET nh_coins = nh_coins + :c WHERE id = :u"), {"c": rep.refunded, "u": user_id})
    return rep


def _json(d: dict) -> str:
    import json

    return json.dumps(d, ensure_ascii=False)


# --- заявки: вызов, итог, срок ---


class ClaimError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def open_claims(session: AsyncSession, user_id: int) -> list[tuple[int, int, str, datetime, bool]]:
    """Открытые заявки игрока: (id, номер района, город, срок, идёт ли уже вызов)."""
    rows = (await session.execute(text(
        "SELECT l.id, d.number, c.name, l.expires_at, l.challenge_id IS NOT NULL FROM league_claims l "
        "JOIN districts d ON d.id = l.district_id JOIN cities c ON c.id = d.city_id "
        "WHERE l.user_id = :u AND l.status = :s AND l.expires_at > now() ORDER BY l.id"
    ), {"u": user_id, "s": CLAIM_OPEN})).all()
    return [(int(a), int(b), str(c), d, bool(e)) for a, b, c, d, e in rows]


async def start_claim(session: AsyncSession, redis, user, claim_id: int):
    """Бесплатный вызов по заявке: без КД сражений, в обход ограничений фазы. Район к этому времени стал ничейным —
    забрать сразу со зданиями. Коммитит. → `ChallengeIssued` или None (район забран без боя)."""
    from bot.services.district.challenge import _accept_window, _create_district_challenge
    from bot.services.district.district import get_row

    claim = (await session.execute(text(
        "SELECT id, district_id, buildings, status, expires_at, challenge_id FROM league_claims WHERE id = :i AND user_id = :u FOR UPDATE"
    ), {"i": claim_id, "u": user.id})).first()
    if claim is None or claim[3] != CLAIM_OPEN:
        raise ClaimError("gone")
    if claim[4] <= datetime.now(timezone.utc):
        raise ClaimError("expired")
    if claim[5] is not None:
        raise ClaimError("in_progress")
    row = await get_row(session, claim[1])
    if row is None:
        raise ClaimError("gone")
    if row.owner_id is None:  # хозяин ушёл — район свободен, ставим здания без боя
        await session.execute(text("UPDATE districts SET owner_id = :u, captured_at = now() WHERE id = :d"), {"u": user.id, "d": row.id})
        await _place(session, user.id, row.id, claim[2])
        await session.execute(text("UPDATE league_claims SET status = :s WHERE id = :i"), {"s": CLAIM_WON, "i": claim_id})
        await session.commit()
        return None
    if row.owner_id == user.id:
        raise ClaimError("gone")
    if row.city_id != user.city_id:
        raise ClaimError("city")
    window = await _accept_window(session, user.id, row.owner_id)
    issued = await _create_district_challenge(session, user, row, row.id, window)
    await session.execute(text("UPDATE league_claims SET challenge_id = :c WHERE id = :i"), {"c": issued.challenge_id, "i": claim_id})
    await session.commit()
    return issued


async def _place(session: AsyncSession, user_id: int, district_id: int, buildings: dict) -> int:
    """Поставить отложенные здания на район — сколько влезет (вместимость игрока), остаток — NHCoin. → возврат."""
    from bot.services.business.business import _capacity_per_district

    level = int(await session.scalar(text("SELECT business_capacity FROM users WHERE id = :u"), {"u": user_id}) or 0)
    free = max(0, _capacity_per_district(level) - int(await session.scalar(text(
        "SELECT count(*) FROM businesses WHERE district_id = :d"), {"d": district_id}) or 0))
    back: dict[str, int] = {}
    for t, n in sorted((buildings or {}).items(), key=lambda kv: -BUSINESS_BUILD_COST.get(kv[0], 0)):  # дорогие — первыми
        put = min(int(n), free)
        for _ in range(put):
            await session.execute(text("INSERT INTO businesses (district_id, type) VALUES (:d, :t)"), {"d": district_id, "t": t})
        free -= put
        if int(n) > put:
            back[t] = int(n) - put
    refund = refund_for(back)
    if refund:
        await session.execute(text("UPDATE users SET nh_coins = nh_coins + :c WHERE id = :u"), {"c": refund, "u": user_id})
    return refund


async def settle_claim(session: AsyncSession, challenge_id: int, won: bool, captured: bool) -> None:
    """Итог вызова по заявке (из `settle_challenge`, до его commit): победа с захватом — здания на район,
    иначе — NHCoin. НЕ коммитит."""
    claim = (await session.execute(text(
        "SELECT id, user_id, district_id, buildings FROM league_claims WHERE challenge_id = :c AND status = :s FOR UPDATE"
    ), {"c": challenge_id, "s": CLAIM_OPEN})).first()
    if claim is None:
        return
    if won and captured:
        await _place(session, int(claim[1]), int(claim[2]), claim[3])
        status = CLAIM_WON
    else:
        refund = refund_for(claim[3] or {})
        if refund:
            await session.execute(text("UPDATE users SET nh_coins = nh_coins + :c WHERE id = :u"), {"c": refund, "u": claim[1]})
        status = CLAIM_LOST
    await session.execute(text("UPDATE league_claims SET status = :s WHERE id = :i"), {"s": status, "i": claim[0]})


async def sweep_expired(session: AsyncSession) -> list[tuple[int, int]]:
    """Заявки, у которых вышел срок и нет идущего вызова, — здания NHCoin; вызов по заявке отменён (игрок ушёл
    из города и т.п.) — заявка снова ждёт вызова, пока не истечёт срок. Коммитит. → [(игрок, возврат)]."""
    from bot.constant.district import CHALLENGE_PENDING

    await session.execute(text(
        "UPDATE league_claims l SET challenge_id = NULL FROM district_challenges c "
        "WHERE l.status = :s AND l.challenge_id = c.id AND c.status <> :p AND c.attacker_won IS NULL"
    ), {"s": CLAIM_OPEN, "p": CHALLENGE_PENDING})
    rows = (await session.execute(text(
        "UPDATE league_claims SET status = :e WHERE status = :s AND expires_at <= now() AND challenge_id IS NULL "
        "RETURNING user_id, buildings"
    ), {"e": CLAIM_EXPIRED, "s": CLAIM_OPEN})).all()
    out = []
    for uid, buildings in rows:
        refund = refund_for(buildings or {})
        if refund:
            await session.execute(text("UPDATE users SET nh_coins = nh_coins + :c WHERE id = :u"), {"c": refund, "u": uid})
        out.append((int(uid), refund))
    await session.commit()
    return out


__all__ = ["CLAIM_HOURS", "ClaimError", "MoveReport", "move_on_promotion", "open_claims", "settle_claim", "start_claim", "sweep_expired",
           "CLAIM_LOST", "CLAIM_EXPIRED"]
