"""Расширение профиля для Mini App: онлайн, портрет, прогресс до следующей фазы, сводка
развития (родословная/путь/техника/гений, в т.ч. второе тело) и донат-баланс.

Только чтение. Бот этих данных на экране профиля не показывает — поэтому отдельный модуль,
а не поля `ProfileView` (его собирает и хендлер бота)."""
from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE
from bot.constant.card import POS_LEADER
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG
from bot.db.repositories import card as card_repo
from bot.db.repositories import donate as donate_repo
from bot.db.repositories import phase as phase_repo
from bot.db.repositories import profile as profile_repo
from bot.services.extra import get_army_stats
from bot.services.genius import get_view as get_genius_view
from bot.services.unique_path import get_view as get_path_view
from bot.services.unique_technique import get_view as get_technique_view

ONLINE_WINDOW_MINUTES = 15


@dataclass(frozen=True, slots=True)
class PhaseProgress:
    target_phase: str  # фаза, к которой идёт игрок
    current: int  # районов взято в зоне цели
    total: int
    scope: str  # "city" | "country"


@dataclass(frozen=True, slots=True)
class DevItem:
    code: str
    level: int


@dataclass(frozen=True, slots=True)
class ProfileExtras:
    online: int
    avatar_image: str | None
    donate_balance: int
    phase_progress: PhaseProgress | None
    bloodline: DevItem | None
    bloodline2: DevItem | None
    path: DevItem | None
    path2: DevItem | None
    technique: DevItem | None
    genius: DevItem | None
    second_body: bool
    attack_power: int
    defense_power: int


async def _avatar(session: AsyncSession, user_id: int) -> str | None:
    positions = {p.position: p.card_code for p in await card_repo.list_positions(session, user_id)}
    code = positions.get(POS_LEADER)
    card = CARD_BY_CODE.get(code) if code else None
    if card is not None and card.image:
        return card.image
    return None


async def _phase_progress(session: AsyncSession, user_id: int, phase: str, city_id: int | None) -> PhaseProgress | None:
    if phase == PHASE_GANG and city_id is not None:
        total = await profile_repo.count_districts_in_city(session, city_id)
        left = await phase_repo.count_not_owned_in_city(session, city_id, user_id)
        return PhaseProgress(PHASE_CIRCLE, max(total - left, 0), total, "city")
    if phase == PHASE_CIRCLE:
        current = await phase_repo.get_phase(session, user_id)
        country = current[1] if current else None
        if country is not None:
            total = await profile_repo.count_districts_in_country(session, country)
            left = await phase_repo.count_not_owned_in_country(session, user_id=user_id, country_code=country)
            return PhaseProgress(PHASE_FIST, max(total - left, 0), total, "country")
    return None


async def get_extras(
    session: AsyncSession, redis: Redis, user_id: int, *, phase: str, city_id: int | None, bloodline: DevItem | None
) -> ProfileExtras:
    army = await get_army_stats(session, user_id)
    body = await donate_repo.body_state(session, user_id)
    second_body = bool(body and body[0])
    path_view = await get_path_view(session, redis, user_id)
    tech_view = await get_technique_view(session, redis, user_id)
    genius_view = await get_genius_view(session, redis, user_id)

    def pick(active: str | None, owned: dict[str, int]) -> DevItem | None:
        return DevItem(active, owned.get(active, 1)) if active else None

    bloodline2 = DevItem(body[3], body[4]) if second_body and body[3] else None
    path2_code = body[1] if second_body else None
    return ProfileExtras(
        online=await profile_repo.count_online(session, ONLINE_WINDOW_MINUTES),
        avatar_image=await _avatar(session, user_id),
        donate_balance=await donate_repo.balance(session, user_id),
        phase_progress=await _phase_progress(session, user_id, phase, city_id),
        bloodline=bloodline,
        bloodline2=bloodline2,
        path=pick(path_view.active, path_view.owned),
        path2=pick(path2_code, path_view.owned),
        technique=pick(tech_view.active, tech_view.owned),
        genius=pick(genius_view.active, genius_view.owned),
        second_body=second_body,
        attack_power=army.attack.power,
        defense_power=army.defense.power,
    )
