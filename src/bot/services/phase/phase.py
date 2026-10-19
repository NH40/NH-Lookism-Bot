"""Фазы — банда -> круг -> кулак (император), переходы по захвату города/страны (сервис).

raw-notes «Фазы» + пользователь 2026-09-29/2026-10-01 (`docs/design/fist_emperor.md`):

- Банда, чей захват закрыл весь свой город, — круг. Фаза не откатывается от потери районов.
- Круг, взявший все районы всех городов страны, — **Император**, его банда — **Кулак**
  (фаза `fist`). **Коронация** (`crown`): все города страны платят ему, его районы
  освобождаются, здания уходят во «владения» — доход остаётся.
- **У страны один император.** Если трон занят — коронации нет, вместо неё обязательный
  **бой за трон** (`services/district/throne.py` — бои живут в домене district); здесь только
  сигнал `Promotion.throne_incumbent`.

`check_promotion()` вызывается ПОСЛЕ каждого успешного захвата, в той же транзакции:
PvE-захват района, PvP-вызов (оба масштаба), бой круга с ботами города.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG
from bot.db.repositories import phase as phase_repo


@dataclass(frozen=True, slots=True)
class Promotion:
    phase: str | None = None  # новая фаза (None — без перехода)
    throne_incumbent: int | None = None  # страна взята, но трон занят — бой с этим императором
    # Страна взята, но часть её городов держат ЧУЖИЕ императоры (отбили в войнах) — сначала бои за
    # освобождение с каждым по очереди, крупнейший первым (пользователь 2026-10-14).
    foreign_holders: tuple[int, ...] = ()


async def check_promotion(session: AsyncSession, user_id: int, city_id: int) -> Promotion:
    """Повышает фазу, если захват в `city_id` закрыл условие. НЕ коммитит (правило 10)."""
    current = await phase_repo.get_phase(session, user_id)
    if current is None:
        return Promotion()
    phase, country_code = current
    promoted: str | None = None

    if phase == PHASE_GANG and await phase_repo.count_not_owned_in_city(session, city_id, user_id) == 0:
        if await phase_repo.promote(session, user_id, PHASE_GANG, PHASE_CIRCLE):
            phase = promoted = PHASE_CIRCLE

    if (
        phase == PHASE_CIRCLE
        and country_code is not None
        and await phase_repo.count_not_owned_in_country(session, country_code, user_id) == 0
    ):
        holders = await phase_repo.foreign_holders(session, country_code)
        if holders:
            return Promotion(phase=promoted, foreign_holders=tuple(uid for uid, _ in holders))
        incumbent = await phase_repo.country_emperor(session, country_code, exclude_user_id=user_id)
        if incumbent is not None:
            return Promotion(phase=promoted, throne_incumbent=incumbent)
        await crown_with_autobuild(session, user_id, country_code)
        promoted = PHASE_FIST

    return Promotion(phase=promoted)


async def crown(session: AsyncSession, user_id: int) -> None:
    """Коронация (после выигранного боя за трон). НЕ коммитит."""
    country_code = (await phase_repo.get_phase(session, user_id))[1]
    await crown_with_autobuild(session, user_id, country_code)


async def crown_with_autobuild(session: AsyncSession, user_id: int, country_code: str) -> int:
    """Единая точка коронации: сначала бесплатная застройка свободных мест (`autobuild_for_crown`),
    потом районы освобождаются, а здания уходят во владения. → сколько построено. НЕ коммитит."""
    from bot.services.business import autobuild_for_crown

    built = await autobuild_for_crown(session, user_id)
    await phase_repo.crown(session, user_id, country_code)
    return built


async def demote_to_gang(session: AsyncSession, user_id: int) -> None:
    """Проигравший бой за трон — в банду, без районов и бизнеса. НЕ коммитит."""
    await phase_repo.demote_to_gang(session, user_id)


def is_city_conqueror(phase: str) -> bool:
    """Круг и император районы по одному не берут (банда — берёт)."""
    return phase != PHASE_GANG


def can_conquer_cities(phase: str) -> bool:
    """Город целиком берёт только круг; император воюет с другими императорами (позже)."""
    return phase == PHASE_CIRCLE


def is_emperor(phase: str) -> bool:
    return phase == PHASE_FIST
