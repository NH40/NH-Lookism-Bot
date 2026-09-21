"""Банда игрока — название, состав (9 позиций), статисты (лагеря) (репозиторий).

Пока — только название (см. `db/models/gang.py`). Состав/статисты/уникальная коллекция
появятся здесь по мере реализации `recruit`/`extra`/`card` — не додумывать заранее (см.
CLAUDE.md, feedback про это — многое в разделе «Банда» raw-notes недоспецифицировано).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.gang import Gang


async def create(session: AsyncSession, *, user_id: int, name: str) -> Gang:
    """Лист-операция (правило 10) — коммитит сама. Onboarding уже гарантирует, что банда
    создаётся ровно один раз (см. `services/gang.create_gang` — вызывающий сервис не
    даёт повторно создать банду тому, у кого она уже есть)."""
    gang = Gang(user_id=user_id, name=name)
    session.add(gang)
    await session.commit()
    return gang


async def get_by_user(session: AsyncSession, user_id: int) -> Gang | None:
    return await session.get(Gang, user_id)
