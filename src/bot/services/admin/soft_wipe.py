"""Мягкий вайп (пользователь 2026-11-20, после багоюза кланов: вербовка Гапрёна + УИ и абуз денег/контрактов).

ОСТАЁТСЯ: техника, путь, мастерство, характеристики, гениальность, родословные, пробуждения, донат, абсолюты,
прокачка бизнеса (уровень и вместимость), тикеты и прочие ресурсы, кланы с участниками и клановые войны.
ИЗЫМАЕТСЯ: все районы и здания (районы — ботам), империи (все — в фазу банды), все статисты и контракты статистов,
все уникальные карты кроме абсолютов, NHCoin (на стартовые; вклады NHCoin, капитал банков, казна империй, стеки
покера), статисты и NHCoin в ячейках и на бирже, клановые земли/постройки/рота/казна (как в патче), кредиты
(сгорают, банкиру — 10% невозвращённого).
Перед сбросом — перераспределение по лигам по текущим результатам.

Запуск: `python manager.py soft_wipe --yes` (сначала делает бэкап). НЕ запускается сам.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)


@dataclass
class SoftWipeReport:
    league_moved: int = 0
    loans_compensated: int = 0
    counts: dict[str, int] = field(default_factory=dict)


async def _refund_escrow(session: AsyncSession) -> None:
    """Биржа: ресурсы (кроме NHCoin) из залога возвращаются владельцам, статисты и NHCoin сгорают; всё снимается."""
    from bot.constant.resource import ITEM_RESOURCE, RES_COINS
    from bot.services.resource import grant

    refunds = []
    for table, owner in (("exchange_lots", "seller_id"), ("exchange_auctions", "seller_id"), ("exchange_trades", "from_id")):
        refunds += (await session.execute(text(
            f"SELECT {owner}, item_code, amount FROM {table} WHERE item_kind = :k AND item_code <> :c"),
            {"k": ITEM_RESOURCE, "c": RES_COINS})).all()
    # Ставки на аукционах — в ресурсе цены; NHCoin сгорают, остальное — назад ставившему.
    refunds += (await session.execute(text(
        "SELECT bidder_id, price_res, current_bid FROM exchange_auctions WHERE bidder_id IS NOT NULL AND current_bid > 0 AND price_res <> :c"),
        {"c": RES_COINS})).all()
    for uid, code, amount in refunds:
        if uid and amount > 0:
            await grant(session, uid, code, amount)
    for table in ("exchange_lots", "exchange_auctions", "exchange_trades"):
        await session.execute(text(f"DELETE FROM {table}"))


async def run_soft_wipe(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> SoftWipeReport:
    from bot.config.empire import EMPIRE_TAX_DEFAULT_PERCENT
    from bot.constant.absolute import ABSOLUTES
    from bot.config.clan import CLAN_START_LANDS
    from bot.constant.phase import PHASE_GANG
    from bot.db.repositories.clan import reset_for_patch as reset_clans
    from bot.db.repositories.top.top import reset_powers
    from bot.services.admin.live_config import get as live_get
    from bot.services.admin.patch import _wipe_loans
    from bot.services.league import redistribute
    from bot.services.resource import grant

    report = SoftWipeReport()
    # 1. Лиги — по текущим результатам (пока доход и мощь ещё не сброшены).
    result = await redistribute(session_factory, redis)
    report.league_moved = len(result.moved)
    # 2. Кредиты сгорают, банкирам — 10% невозвращённого (начислим после сброса NHCoin).
    compensation = await _wipe_loans(session_factory)
    report.loans_compensated = len(compensation)
    absolutes = list(ABSOLUTES)
    # 3. Сам сброс — одной транзакцией, запросами по множествам.
    async with session_factory() as session:
        for name, sql, params in (
            ("buildings", "DELETE FROM businesses", {}),
            ("districts", "UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE owner_id IS NOT NULL", {}),
            ("emperors", "UPDATE cities SET emperor_id = NULL WHERE emperor_id IS NOT NULL", {}),
            ("tax_overrides", "DELETE FROM emperor_tax_overrides", {}),
            ("challenges", "DELETE FROM district_challenges WHERE status = 'pending'", {}),
            ("emperor_wars", "DELETE FROM emperor_wars WHERE status = 'pending'", {}),
            ("raids", "DELETE FROM raids WHERE status = 'pending'", {}),
            ("statists", "DELETE FROM extras", {}),
            ("contracts", "DELETE FROM statist_contracts", {}),
            ("cards", "DELETE FROM card_stacks WHERE card_code <> ALL(:abs)", {"abs": absolutes}),
            ("positions", "DELETE FROM card_positions WHERE card_code IS NULL OR card_code <> ALL(:abs)", {"abs": absolutes}),
            ("deposits_coins", "DELETE FROM deposits WHERE resource = 'coins'", {}),
            ("bank_capital", "UPDATE banks SET capital = 0", {}),
            ("storage", "UPDATE storage_cells SET item_kind = '', item_code = '', amount = 0 "
                        "WHERE item_kind = 'statist' OR (item_kind = 'res' AND item_code = 'coins')", {}),
            ("poker", "UPDATE poker_players SET stack = 0, leaving = true", {}),
            ("users", "UPDATE users SET phase = :phase, nh_coins = :coins, coins_accrued_at = now(), "
                      "empire_tax_percent = :tax, empire_collected = 0", {"phase": PHASE_GANG, "coins": live_get("starting_nh_coins"),
                                                                         "tax": EMPIRE_TAX_DEFAULT_PERCENT}),
        ):
            r = await session.execute(text(sql), params)
            report.counts[name] = r.rowcount or 0
        await _refund_escrow(session)
        # Кланы — как в патче (земли, постройки, рота, казна), но клановые войны продолжаются (объявление 2026-11-20).
        await reset_clans(session, CLAN_START_LANDS, keep_wars=True)
        for uid, amount in compensation.items():
            await grant(session, uid, "coins", amount)
        await reset_powers(session)
        await session.commit()
    # 4. Идущие онлайн-бои ссылаются на снятые армии — снимаем.
    keys = [k async for k in redis.scan_iter("arena:*")]
    if keys:
        await redis.delete(*keys)
    log.warning("Soft wipe done: %s", report)
    return report
