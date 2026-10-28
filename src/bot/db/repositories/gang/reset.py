"""Сброс прогресса игрока — удаление банды и пробуждение (репозиторий).

Один набор запросов по множествам (правило 3), НЕ коммитит — коммитит сервис одним разом
(правило 10): сброс либо проходит целиком, либо не проходит вовсе. Общая часть —
`_PROGRESS_STATEMENTS`; удаление банды дополнительно стирает саму банду и страну/город
(новый онбординг), пробуждение — оставляет их и перебрасывает потенциал.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.absolute import ABSOLUTES
from bot.config.empire import EMPIRE_TAX_DEFAULT_PERCENT
from bot.constant.district import CHALLENGE_PENDING
from bot.constant.phase import PHASE_GANG

_PROGRESS_STATEMENTS = (
    # Здания на районах игрока — удаляются (районы возвращаются ботам пустыми).
    "DELETE FROM businesses WHERE district_id IN (SELECT id FROM districts WHERE owner_id = :uid)",
    # Владения императора (здания без района) и города, которые ему платили.
    "DELETE FROM businesses WHERE holder_id = :uid",
    "UPDATE cities SET emperor_id = NULL WHERE emperor_id = :uid",
    # Персональные налоги: и его как императора, и ему как игроку (уедет в другой город).
    "DELETE FROM emperor_tax_overrides WHERE emperor_id = :uid OR user_id = :uid",
    "UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE owner_id = :uid",
    # Висящие вызовы с участием игрока — снимаются (история разрешённых остаётся).
    "DELETE FROM district_challenges WHERE status = :pending AND (attacker_id = :uid OR defender_id = :uid)",
    "DELETE FROM extras WHERE user_id = :uid",
    # Абсолюты не пропадают даже при удалении банды (пользователь 2026-10-16).
    "DELETE FROM card_stacks WHERE user_id = :uid AND card_code NOT IN (" + ", ".join(f"'{c}'" for c in ABSOLUTES) + ")",
    "DELETE FROM card_positions WHERE user_id = :uid",
    "DELETE FROM mastery_quests WHERE user_id = :uid",
    # Системы развития: путь и уникальные техники теряются (пользователь: «до удаления
    # банды… путь будет таким, каким выпал»; техник нет в списке сохраняемого). Гениальности,
    # родословная, фрагменты и капли крови остаются.
    "DELETE FROM user_techniques WHERE user_id = :uid",
    "DELETE FROM user_paths WHERE user_id = :uid",
    "DELETE FROM battle_memory WHERE user_id = :uid",
    "DELETE FROM statist_contracts WHERE user_id = :uid",
    "DELETE FROM dev_quests WHERE user_id = :uid AND kind IN ('teacher', 'conviction', 'path', 'school', 'tech_level')",
    # Учителя статистов — часть прогресса (как бизнес): при сбросе снова искать на карте.
    "DELETE FROM user_schools WHERE user_id = :uid",
    "DELETE FROM user_potions WHERE user_id = :uid",
    # Вклады сгорают с прогрессом — иначе через них проносили бы NHCoin мимо сброса.
    "DELETE FROM deposits WHERE user_id = :uid",
    # Стек за покерным столом сгорает (иначе NHCoin проносили бы через сброс за столом);
    # игрок встаёт после текущей раздачи.
    "UPDATE poker_players SET stack = 0, leaving = true WHERE user_id = :uid",
    # Биржа: залог игрока сгорает (лоты, аукционы, исходящие обмены), его ставка-лидер на
    # чужих аукционах — тоже (аукцион снова без ставок).
    "DELETE FROM exchange_lots WHERE seller_id = :uid",
    "DELETE FROM exchange_auctions WHERE seller_id = :uid",
    "DELETE FROM exchange_trades WHERE from_id = :uid",
    "UPDATE exchange_auctions SET bidder_id = NULL, current_bid = 0 WHERE bidder_id = :uid",
    # Ячейки хранения: вещи сгорают при пробуждении и удалении банды (пользователь
    # 2026-10-04), купленные ячейки остаются.
    "UPDATE storage_cells SET item_kind = '', item_code = '', amount = 0 WHERE user_id = :uid",
)
_PROGRESS_COLUMNS = """
        phase = :phase,
        nh_coins = :coins, coins_accrued_at = now(), business_level = 0, business_capacity = 0,
        stat_strength = 0, stat_speed = 0, stat_endurance = 0, stat_agility = 0, dev_points = 0,
        mastery_strength = 0, mastery_speed = 0, mastery_endurance = 0, mastery_technique = 0,
        tickets_count = :tickets, tickets_updated_at = now(),
        empire_tax_percent = :empire_tax, empire_collected = 0, influence_banked = 0,
        active_technique = NULL, active_path = NULL, active_path2 = NULL, path_stage = 0, path_points = 0, path_point_gates = '{}'
"""
_STATEMENTS = _PROGRESS_STATEMENTS + (
    "DELETE FROM gangs WHERE user_id = :uid",
    # Сам игрок: страна/город — заново онбординг; потенциал НЕ трогаем (пользователь
    # 2026-10-01: сохраняются потенциал, пробуждение, родословная, талант).
    "UPDATE users SET country_code = NULL, city_id = NULL," + _PROGRESS_COLUMNS + "WHERE id = :uid",
)
# Пробуждение: банда, страна и город остаются (игрок перерождается на месте); потенциал —
# новый, этап пробуждения +1, капли крови — награда.
_AWAKEN_STATEMENTS = _PROGRESS_STATEMENTS + (
    "UPDATE users SET potential = :potential, awakening_level = awakening_level + 1, "
    "blood_drops = blood_drops + :blood," + _PROGRESS_COLUMNS + "WHERE id = :uid AND awakening_level = :current",
)


async def reset_player(session: AsyncSession, user_id: int, *, nh_coins: int, tickets: int) -> None:
    await session.execute(text("SELECT id FROM users WHERE id = :uid FOR UPDATE"), {"uid": user_id})
    params = {"uid": user_id, "pending": CHALLENGE_PENDING, "phase": PHASE_GANG, "coins": nh_coins, "tickets": tickets,
              "empire_tax": EMPIRE_TAX_DEFAULT_PERCENT}
    for sql in _STATEMENTS:
        await session.execute(text(sql), params)


async def awaken_player(
    session: AsyncSession, user_id: int, *, nh_coins: int, tickets: int, potential: str, blood: int, current_level: int
) -> None:
    """Сброс прогресса при пробуждении. Последний UPDATE условный по текущему этапу — двойное
    подтверждение не пробудит дважды (вызывающий проверяет результат по `awakening_level`)."""
    await session.execute(text("SELECT id FROM users WHERE id = :uid FOR UPDATE"), {"uid": user_id})
    params = {"uid": user_id, "pending": CHALLENGE_PENDING, "phase": PHASE_GANG, "coins": nh_coins, "tickets": tickets,
              "empire_tax": EMPIRE_TAX_DEFAULT_PERCENT, "potential": potential, "blood": blood, "current": current_level}
    for sql in _AWAKEN_STATEMENTS:
        await session.execute(text(sql), params)
