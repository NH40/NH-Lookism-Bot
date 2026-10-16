"""Пробуждение (сервис). Дизайн — `docs/design/development_systems.md`, «Пробуждение».

Пользователь 2026-10-02:
- на этапе **кулака** (император) игрок выполняет квест → открывается пробуждение;
- пробуждение **сбрасывает прокачку** (этап, бизнес — «всё»): фаза → банда, районы, бизнес,
  армия и уники, характеристики (до пола родословной), мастерство, путь, уникальные
  техники, NHCoin и тикеты; **остаются** гениальности, родословная, фрагменты, капли крови,
  само пробуждение, а также банда, страна и город (перерождение на месте, без онбординга);
- **10 этапов**; каждый **поднимает минимальный потенциал** — потенциал перебрасывается
  заново, но не ниже пола (`potential_floor_index`);
- каждый этап — **множитель ко всем бафам** систем развития (`config/development.
  awakening_multiplier`) и **свои бафы** (`config/awakening.LEVELS`), а также **капли крови**.

Квест — через общий механизм заданий (`services/dev_quest`, вид `awakening`, ref — номер
следующего этапа): выдаётся лениво, как только игрок — император; прогресс — с этого
момента. Подтверждение — два нажатия с таймером (необратимо), как у удаления банды.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import awaken_confirm
from bot.config.awakening import (
    AWAKEN_CONFIRM_SECONDS,
    AWAKENING_MAX,
    awakening_blood_drops,
    awakening_quest,
    potential_floor_index,
)
from bot.config.development import awakening_multiplier
from bot.config.game import NH_COINS_STARTING, TICKET_STARTING
from bot.constant.activity import ACT_DEVELOPMENT
from bot.constant.characteristic import POTENTIAL_ORDER
from bot.constant.dev_quest import QUEST_AWAKENING
from bot.db.models.user import User
from bot.db.repositories.gang import awaken_player
from bot.db.repositories.phase import get_phase
from bot.services.activity import log as log_activity
from bot.services.bloodline import apply_effects as apply_bloodline_effects
from bot.services.donate import apply_all as apply_donate
from bot.services.build import get_build
from bot.services.characteristic import roll_potential
from bot.services.dev_quest import QuestView, claim, list_active, start
from bot.services.phase import is_emperor
from bot.texts.activity import LOG_AWAKENING


class NotEmperorError(Exception):
    """Пробуждение открывается на этапе кулака."""


class AwakeningMaxedError(Exception):
    pass


class QuestNotCompleteError(Exception):
    pass


class ConfirmExpiredError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AwakeningView:
    level: int
    multiplier: float
    next_multiplier: float
    is_emperor: bool
    quest: QuestView | None
    next_floor: str  # минимальный потенциал после следующего пробуждения
    next_blood: int
    maxed: bool

    @property
    def ready(self) -> bool:
        return self.is_emperor and not self.maxed and self.quest is not None and self.quest.complete


@dataclass(frozen=True, slots=True)
class AwakenResult:
    level: int
    potential: str
    blood: int
    multiplier: float


def roll_with_floor(level: int, rng: random.Random | None = None) -> str:
    """Новый потенциал при пробуждении: случайный по стартовым весам, но не ниже пола этапа."""
    rolled = roll_potential(rng)
    floor = potential_floor_index(level)
    return POTENTIAL_ORDER[max(POTENTIAL_ORDER.index(rolled), floor)]


async def _level(session: AsyncSession, user_id: int) -> int:
    user = await session.get(User, user_id, populate_existing=True)
    return user.awakening_level if user else 0


async def ensure_quest(session: AsyncSession, user_id: int) -> QuestView | None:
    """Квест на следующий этап: если игрок — император и квеста ещё нет, выдать. Коммитит,
    если выдал. → активный квест (или None)."""
    level = await _level(session, user_id)
    if level >= AWAKENING_MAX:
        return None
    ref = str(level + 1)
    quests = {q.ref: q for q in await list_active(session, user_id, QUEST_AWAKENING)}
    if ref in quests:
        return quests[ref]
    current = await get_phase(session, user_id)
    if current is None or not is_emperor(current[0]):
        return None
    if await start(session, user_id, QUEST_AWAKENING, ref, awakening_quest(level + 1)):
        await session.commit()
    quests = {q.ref: q for q in await list_active(session, user_id, QUEST_AWAKENING)}
    return quests.get(ref)


async def get_view(session: AsyncSession, user_id: int) -> AwakeningView:
    quest = await ensure_quest(session, user_id)
    level = await _level(session, user_id)
    current = await get_phase(session, user_id)
    maxed = level >= AWAKENING_MAX
    return AwakeningView(
        level=level,
        multiplier=awakening_multiplier(level),
        next_multiplier=awakening_multiplier(min(level + 1, AWAKENING_MAX)),
        is_emperor=current is not None and is_emperor(current[0]),
        quest=quest,
        next_floor=POTENTIAL_ORDER[potential_floor_index(min(level + 1, AWAKENING_MAX))],
        next_blood=awakening_blood_drops(min(level + 1, AWAKENING_MAX)),
        maxed=maxed,
    )


async def request(session: AsyncSession, redis: Redis, user_id: int) -> int:
    """Первое нажатие: проверить готовность и поставить флаг подтверждения. → секунд на «Да»."""
    view = await get_view(session, user_id)
    if view.maxed:
        raise AwakeningMaxedError
    if not view.is_emperor:
        raise NotEmperorError
    if not view.ready:
        raise QuestNotCompleteError
    await redis.set(awaken_confirm(user_id), "1", ex=AWAKEN_CONFIRM_SECONDS)
    return AWAKEN_CONFIRM_SECONDS


async def awaken(session: AsyncSession, redis: Redis, user_id: int, rng: random.Random | None = None) -> AwakenResult:
    """Второе нажатие: флаг подтверждения снимается атомарно (`GETDEL`) — повтор не пройдёт;
    квест закрывается и сброс выполняется одной транзакцией (правило 10). Коммитит."""
    if not await redis.getdel(awaken_confirm(user_id)):
        raise ConfirmExpiredError
    current = await get_phase(session, user_id)
    if current is None or not is_emperor(current[0]):
        raise NotEmperorError
    level = await _level(session, user_id)
    if level >= AWAKENING_MAX:
        raise AwakeningMaxedError
    if await claim(session, user_id, QUEST_AWAKENING, str(level + 1)) is None:
        raise QuestNotCompleteError
    new_level = level + 1
    potential = roll_with_floor(new_level, rng)
    blood = round(awakening_blood_drops(new_level) * (1 + (await get_build(session, user_id)).eco.blood_bonus))
    await awaken_player(
        session, user_id, nh_coins=NH_COINS_STARTING, tickets=TICKET_STARTING,
        potential=potential, blood=blood, current_level=level,
    )
    if await _level(session, user_id) != new_level:
        await session.rollback()
        raise QuestNotCompleteError
    # Родословная остаётся — её пол характеристик и выданная ею техника — тоже.
    await apply_bloodline_effects(session, user_id)
    await apply_donate(session, user_id)  # купленные за донат техники/гении/уровни — обратно
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_AWAKENING.format(level=new_level))
    await session.commit()
    return AwakenResult(level=new_level, potential=potential, blood=blood, multiplier=awakening_multiplier(new_level))
