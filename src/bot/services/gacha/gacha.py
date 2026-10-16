"""Крутки за тикеты — получение уникального персонажа (сервис).

Подтверждено пользователем 2026-09-30: 1 тикет = 1 крутка; чем выше редкость — тем реже
(шансы — `config/card.RARITY_CHANCE_PERCENT`, Абсолюты — тоже в крутке, 0.01%); внутри
редкости карта выбирается равновероятно. Выпавшая копия идёт в армию — в лагерь атаки, как
новые статисты с вербовки; дубликат — просто ещё одна копия в стопке.

Составная операция (правило 10): Redis-лок на клик (правило 2) → атомарное списание тикета
вместе с регеном → добавление копии → один commit. Лок снимается сразу после.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.card import CARDS_BY_RARITY, RARITY_CHANCE_PERCENT, CardDef
from bot.config.game import ACTION_LOCK_MS
from bot.constant.extra import CAMP_ATTACK
from bot.constant.gacha import LOCK_ACTION_ROLL
from bot.db.repositories import card as card_repo
from bot.constant.card import RARITY_INDEX, RARITY_ORDER
from bot.constant.dev_quest import TASK_ROLL
from bot.services.dev_quest import emit as quest_event
from bot.services.build import get_build
from bot.services.ticket import TicketStatus, get_status, refund, spend


class NoTicketsError(Exception):
    def __init__(self, status: TicketStatus) -> None:
        self.status = status


class RollBusyError(Exception):
    """Предыдущая крутка этого игрока ещё обрабатывается (двойной клик)."""


@dataclass(frozen=True, slots=True)
class RollResult:
    card: CardDef
    copies: int  # сколько копий этой карты теперь у игрока всего
    tickets: TicketStatus
    free: bool = False  # тикет вернулся (бесплатная крутка)


def pick_card(rng: random.Random | None = None, luck: float = 0.0) -> CardDef:
    """Редкость по весам, затем карта равновероятно внутри неё. Пустая редкость (карты ещё
    не заведены) — её вес просто не участвует. `luck` — шанс поднять выпавшую редкость на
    ступень (Элита, гений харизмы; не выше 50%) — к ближайшей следующей непустой."""
    rng = rng or random
    rarities = [r for r in RARITY_CHANCE_PERCENT if CARDS_BY_RARITY.get(r)]
    rarity = rng.choices(rarities, weights=[RARITY_CHANCE_PERCENT[r] for r in rarities])[0]
    if luck and rng.random() < min(0.5, luck):
        higher = [r for r in RARITY_ORDER[RARITY_INDEX[rarity] + 1:] if CARDS_BY_RARITY.get(r)]
        if higher:
            rarity = higher[0]
    return rng.choice(CARDS_BY_RARITY[rarity])


async def roll(session: AsyncSession, redis: Redis, user_id: int) -> RollResult:
    key = action_lock(user_id, LOCK_ACTION_ROLL)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise RollBusyError
    try:
        tickets = await spend(session, user_id, 1)
        if tickets is None:
            raise NoTicketsError(await get_status(session, user_id))
        eco = (await get_build(session, user_id)).eco
        card = pick_card(luck=eco.gacha_luck)
        # Бесплатная крутка (Элита): тикет возвращается — копия всё равно выпадает.
        free = bool(eco.gacha_free_roll) and random.random() < min(0.5, eco.gacha_free_roll)
        if free:
            tickets = await refund(session, user_id, 1)
        await card_repo.add_to_stack(session, user_id=user_id, card_code=card.code, camp=CAMP_ATTACK, quantity=1)
        copies = await card_repo.count_copies(session, user_id, card.code)
        await quest_event(session, user_id, TASK_ROLL)
        await session.commit()
        return RollResult(card=card, copies=copies, tickets=tickets, free=free)
    finally:
        await redis.delete(key)
