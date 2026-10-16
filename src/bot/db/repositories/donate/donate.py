"""Донат (репозиторий). Функции записи НЕ коммитят."""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.donate import DonateUnlock


async def insert_payment(
    session: AsyncSession, user_id: int, charge_id: str, provider_id: str, amount_rub: int, coins: int
) -> bool:
    """Платёж + зачисление одним запросом; повторная доставка апдейта (тот же charge_id) — no-op."""
    result = await session.execute(
        text(
            """
            WITH ins AS (
                INSERT INTO payments (user_id, telegram_charge_id, provider_charge_id, amount_rub, coins)
                VALUES (:u, :c, :p, :rub, :coins)
                ON CONFLICT (telegram_charge_id) DO NOTHING
                RETURNING user_id
            )
            UPDATE users SET donate_coins = donate_coins + :coins WHERE id IN (SELECT user_id FROM ins)
            """
        ),
        {"u": user_id, "c": charge_id, "p": provider_id, "rub": amount_rub, "coins": coins},
    )
    return result.rowcount > 0


async def balance(session: AsyncSession, user_id: int) -> int:
    value = (await session.execute(text("SELECT donate_coins FROM users WHERE id = :u"), {"u": user_id})).scalar_one_or_none()
    return value or 0


async def spend(session: AsyncSession, user_id: int, amount: int) -> bool:
    result = await session.execute(
        text("UPDATE users SET donate_coins = donate_coins - :a WHERE id = :u AND donate_coins >= :a"),
        {"u": user_id, "a": amount},
    )
    return result.rowcount > 0


async def buy_second_body(session: AsyncSession, user_id: int, price: int) -> bool:
    result = await session.execute(
        text(
            "UPDATE users SET second_body = true, donate_coins = donate_coins - :p "
            "WHERE id = :u AND NOT second_body AND donate_coins >= :p"
        ),
        {"u": user_id, "p": price},
    )
    return result.rowcount > 0


async def unlocks(session: AsyncSession, user_id: int, kind: str | None = None) -> dict[tuple[str, str], int]:
    query = select(DonateUnlock.kind, DonateUnlock.code, DonateUnlock.level).where(DonateUnlock.user_id == user_id)
    if kind:
        query = query.where(DonateUnlock.kind == kind)
    return {(k, c): lvl for k, c, lvl in (await session.execute(query)).all()}


async def floor(session: AsyncSession, user_id: int, kind: str, code: str) -> int:
    value = await session.scalar(
        select(DonateUnlock.level).where(DonateUnlock.user_id == user_id, DonateUnlock.kind == kind, DonateUnlock.code == code)
    )
    return value or 0


async def add_unlock(session: AsyncSession, user_id: int, kind: str, code: str) -> bool:
    result = await session.execute(
        text("INSERT INTO donate_unlocks (user_id, kind, code, level) VALUES (:u, :k, :c, 1) ON CONFLICT DO NOTHING"),
        {"u": user_id, "k": kind, "c": code},
    )
    return result.rowcount > 0


async def bump_unlock(session: AsyncSession, user_id: int, kind: str, code: str, current: int) -> bool:
    result = await session.execute(
        text("UPDATE donate_unlocks SET level = level + 1 WHERE user_id = :u AND kind = :k AND code = :c AND level = :cur"),
        {"u": user_id, "k": kind, "c": code, "cur": current},
    )
    return result.rowcount > 0


# Вид покупки → таблица полученных позиций (ключи — константы `constant/donate`, не ввод).
_OWNED_TABLES = {"genius": "user_geniuses", "path": "user_paths", "tech": "user_techniques"}


async def raise_owned_level(session: AsyncSession, user_id: int, kind: str, code: str, level: int) -> None:
    """Уровень уже полученной позиции — не ниже купленного."""
    await session.execute(
        text(f"UPDATE {_OWNED_TABLES[kind]} SET level = GREATEST(level, :l) WHERE user_id = :u AND code = :c"),
        {"u": user_id, "c": code, "l": level},
    )


# --- второе тело ---


async def body_state(session: AsyncSession, user_id: int) -> tuple | None:
    """(второе тело, второй путь, первая родословная, вторая родословная, её уровень, капли крови)."""
    return (
        await session.execute(
            text(
                "SELECT second_body, active_path2, bloodline, bloodline2, bloodline2_level, blood_drops "
                "FROM users WHERE id = :u"
            ),
            {"u": user_id},
        )
    ).first()


async def set_active_path2(session: AsyncSession, user_id: int, code: str | None) -> None:
    await session.execute(text("UPDATE users SET active_path2 = :c WHERE id = :u"), {"u": user_id, "c": code})


async def choose_bloodline2(session: AsyncSession, user_id: int, code: str, start_level: int) -> bool:
    result = await session.execute(
        text(
            "UPDATE users SET bloodline2 = :c, bloodline2_level = :l "
            "WHERE id = :u AND second_body AND bloodline2 IS NULL AND bloodline IS DISTINCT FROM :c"
        ),
        {"u": user_id, "c": code, "l": start_level},
    )
    return result.rowcount > 0


async def level_up_bloodline2(session: AsyncSession, user_id: int, current: int, cost: int) -> bool:
    result = await session.execute(
        text(
            "UPDATE users SET bloodline2_level = bloodline2_level + 1, blood_drops = blood_drops - :cost "
            "WHERE id = :u AND bloodline2 IS NOT NULL AND bloodline2_level = :cur AND blood_drops >= :cost"
        ),
        {"u": user_id, "cur": current, "cost": cost},
    )
    return result.rowcount > 0


# --- перенос доната LBP 1.3 ---


async def lbp1_imported(session: AsyncSession) -> bool:
    return bool(await session.scalar(text("SELECT EXISTS(SELECT 1 FROM lbp1_donations)")))


async def lbp1_insert(session: AsyncSession, rows: list[dict]) -> None:
    if rows:
        await session.execute(
            text(
                "INSERT INTO lbp1_donations (tg_id, titles, circles, balance, total) "
                "VALUES (:tg_id, :titles, :circles, :balance, :total) ON CONFLICT (tg_id) DO NOTHING"
            ),
            rows,
        )


async def lbp1_credit(session: AsyncSession, tg_id: int | None = None) -> int:
    """Зачислить ещё не зачисленный донат 1.3 тем, кто уже есть в 2.0 (всем или одному) —
    одним запросом с отметкой `credited_at`. → сколько игроков получили."""
    result = await session.execute(
        text(
            """
            WITH due AS (
                UPDATE lbp1_donations d SET credited_at = now()
                WHERE d.credited_at IS NULL AND EXISTS (SELECT 1 FROM users u WHERE u.id = d.tg_id)
                  AND (CAST(:tg AS bigint) IS NULL OR d.tg_id = CAST(:tg AS bigint))
                RETURNING d.tg_id, d.total
            )
            UPDATE users u SET donate_coins = u.donate_coins + due.total FROM due WHERE u.id = due.tg_id
            """
        ),
        {"tg": tg_id},
    )
    return result.rowcount
