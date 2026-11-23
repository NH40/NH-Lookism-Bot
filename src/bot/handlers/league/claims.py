"""Заявки на районы после перехода в лигу — кнопка «⚔️ Отбить район» (2026-11-23)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.league import CB_LEAGUE_CLAIM_PREFIX

router = Router(name="league_claims")


@router.callback_query(F.data.startswith(CB_LEAGUE_CLAIM_PREFIX))
async def cb_claim(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    """«⚔️ Отбить район» — бесплатный вызов по заявке после перехода в лигу (2026-11-23)."""
    from bot.db.repositories.user import get_by_id
    from bot.handlers.district.district import _announce_challenge
    from bot.services.league.move import ClaimError, start_claim
    from bot.texts.league import CLAIM_ERRORS, CLAIM_TAKEN

    raw = callback.data.removeprefix(CB_LEAGUE_CLAIM_PREFIX)
    user = await get_by_id(session, callback.from_user.id)
    if not raw.isdigit() or user is None:
        await callback.answer()
        return
    try:
        issued = await start_claim(session, redis, user, int(raw))
    except ClaimError as exc:
        await callback.answer(CLAIM_ERRORS.get(exc.code, "Не вышло."), show_alert=True)
        return
    except Exception as exc:  # noqa: BLE001 — гонка вызовов на район и т.п. — понятным текстом
        from bot.handlers.district.district import attack_error_text

        text = attack_error_text(exc)
        if text is None:
            raise
        await callback.answer(text, show_alert=True)
        return
    if issued is None:
        await callback.answer(CLAIM_TAKEN, show_alert=True)
        return
    await callback.answer()
    await _announce_challenge(callback, session, issued)
