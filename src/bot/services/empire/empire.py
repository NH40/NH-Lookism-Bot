"""Император — экран империи, налоги (сервис).

Пользователь 2026-10-01 (`docs/design/fist_emperor.md`): император устанавливает налог
10–50% — общий для всех игроков его городов и персональный для конкретных («одним дороже,
другим дешевле»); налог игрок теряет. Сверху император пассивно получает +10% от дохода
игроков (они его не теряют). Сами деньги текут при зачислении дохода игрока
(`services/business.accrue`); здесь — только настройка ставок и сводка.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.empire import (
    EMPIRE_OVERRIDES_SHOWN,
    EMPIRE_TAX_MAX_PERCENT,
    EMPIRE_TAX_MIN_PERCENT,
    SABOTAGE_RECENT_HOURS,
)
from bot.db.repositories import empire as empire_repo
from bot.db.repositories.empire import EmpireStats, Subject, TaxContext
from bot.db.repositories.phase import get_phase
from bot.services.phase import is_emperor


class NotEmperorError(Exception):
    pass


class InvalidRateError(Exception):
    pass


class SubjectNotFoundError(Exception):
    """Нет такого игрока в городах императора."""


async def _ensure_emperor(session: AsyncSession, user_id: int) -> None:
    current = await get_phase(session, user_id)
    if current is None or not is_emperor(current[0]):
        raise NotEmperorError


def _validate(percent: int) -> None:
    if not EMPIRE_TAX_MIN_PERCENT <= percent <= EMPIRE_TAX_MAX_PERCENT:
        raise InvalidRateError


async def get_emperor(session: AsyncSession, user_id: int) -> TaxContext | None:
    """Император города игрока (None — нет или игрок сам император)."""
    return await empire_repo.get_tax_context(session, user_id)


async def get_overview(session: AsyncSession, user_id: int) -> EmpireStats:
    await _ensure_emperor(session, user_id)
    return await empire_repo.empire_stats(session, user_id, EMPIRE_OVERRIDES_SHOWN, SABOTAGE_RECENT_HOURS)


async def set_global_rate(session: AsyncSession, user_id: int, percent: int) -> None:
    await _ensure_emperor(session, user_id)
    _validate(percent)
    await empire_repo.set_global_rate(session, user_id, percent)
    await session.commit()


@dataclass(frozen=True, slots=True)
class SubjectRate:
    subject: Subject
    percent: int  # действующая ставка игрока
    has_override: bool


async def find_subject(session: AsyncSession, user_id: int, username: str) -> SubjectRate:
    """Игрок империи по юзернейму и его действующая ставка (персональная, иначе общая)."""
    await _ensure_emperor(session, user_id)
    subject = await empire_repo.find_subject(session, user_id, username)
    if subject is None:
        raise SubjectNotFoundError
    override = await empire_repo.get_override(session, user_id, subject.user_id)
    if override is not None:
        return SubjectRate(subject=subject, percent=override, has_override=True)
    stats = await empire_repo.empire_stats(session, user_id, 0)
    return SubjectRate(subject=subject, percent=stats.tax_percent, has_override=False)


async def set_personal_rate(session: AsyncSession, user_id: int, subject_id: int, percent: int | None) -> None:
    """Персональная ставка игроку империи; None — снять (действует общая)."""
    await _ensure_emperor(session, user_id)
    if percent is None:
        await empire_repo.delete_override(session, user_id, subject_id)
    else:
        _validate(percent)
        # Только игроку своей империи (callback_data подделать нельзя, но цель могла уехать).
        context = await empire_repo.get_tax_context(session, subject_id)
        if context is None or context.emperor_id != user_id:
            raise SubjectNotFoundError
        await empire_repo.set_override(session, user_id, subject_id, percent)
    await session.commit()
