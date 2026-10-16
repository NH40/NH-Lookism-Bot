"""Экран «📈 Развитие» — родословная, пробуждение, техники, путь, гениальность (хендлеры).

Пока работает родословная, остальные системы помечены «скоро» и появятся по одной (см.
`docs/design/development_systems.md`). Без выбранной родословной экран сначала просит её
выбрать (игроки, зарегистрированные до её появления).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.handlers.bloodline import prompt_bloodline
from bot.keyboards.development import development_menu
from bot.services.bloodline import get_state
from bot.services.gang import get_gang
from bot.texts.bloodline import bloodline_line
from bot.texts.development import DEVELOPMENT_SCREEN, PATH_LINE_NONE, TECHNIQUE_LINE_NONE
from bot.texts.genius import GENIUS_LINE, GENIUS_LINE_NONE, GENIUS_NAMES
from bot.db.repositories.genius import list_owned as list_owned_geniuses
from bot.db.repositories.user import get_by_id
from bot.services.genius import ensure_genius
from bot.services.unique_path import check_conviction
from bot.db.repositories.unique_path import list_owned as list_owned_paths
from bot.constant.unique_path import PATH_STAGE_CALLED, PATH_STAGE_CONVICTION, PATH_STAGE_OWNED
from bot.texts.unique_path import PATH_LINE, PATH_LINE_CALLED, PATH_LINE_CONVICTION, PATH_NAMES
from bot.keyboards.development import awakening_button, bloodline_button, path_button
from bot.config.development import awakening_multiplier
from bot.texts.awakening import AWAKENING_LINE, AWAKENING_LINE_ZERO
from bot.db.repositories.unique_technique import list_owned as list_owned_techniques
from bot.texts.unique_technique import TECHNIQUE_LINE, TECHNIQUE_NAMES
from bot.keyboards.development import technique_button
from bot.services.intel import get_access as get_intel_access
from bot.keyboards.intel import intel_entry_rows
from bot.utils.formatting import format_number
from bot.texts.profile import NOT_ONBOARDED

router = Router(name="development")


@router.callback_query(F.data == CB_MENU_DEVELOPMENT)
async def cb_development_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    state = await get_state(session, callback.from_user.id)
    if state.code is None:
        await prompt_bloodline(callback.message)
        return
    text, markup = await render_development(session, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


def _path_line(user, level: int) -> str:
    if user.path_stage == PATH_STAGE_OWNED and user.active_path:
        return PATH_LINE.format(name=PATH_NAMES[user.active_path], level=level)
    if user.path_stage == PATH_STAGE_CALLED:
        return PATH_LINE_CALLED
    if user.path_stage == PATH_STAGE_CONVICTION:
        return PATH_LINE_CONVICTION
    return PATH_LINE_NONE


async def render_development(session: AsyncSession, user_id: int):
    """Экран «Развитие» целиком — строки всех систем и фрагменты."""
    await ensure_genius(session, user_id)
    await check_conviction(session, user_id)
    state = await get_state(session, user_id)
    user = await get_by_id(session, user_id)
    genius_level = dict(await list_owned_geniuses(session, user_id)).get(user.active_genius, 0)
    technique_level = dict(await list_owned_techniques(session, user_id)).get(user.active_technique, 0)
    path_level = dict(await list_owned_paths(session, user_id)).get(user.active_path, 0)
    text = DEVELOPMENT_SCREEN.format(
        bloodline_line=bloodline_line(state.code, state.level, state.blood_drops),
        genius_line=GENIUS_LINE.format(name=GENIUS_NAMES[user.active_genius], level=genius_level)
        if user.active_genius
        else GENIUS_LINE_NONE,
        technique_line=TECHNIQUE_LINE.format(name=TECHNIQUE_NAMES[user.active_technique], level=technique_level)
        if user.active_technique
        else TECHNIQUE_LINE_NONE,
        path_line=_path_line(user, path_level),
        awakening_line=AWAKENING_LINE.format(level=user.awakening_level, multiplier=f"{awakening_multiplier(user.awakening_level):g}")
        if user.awakening_level
        else AWAKENING_LINE_ZERO,
        path_fragments=format_number(user.path_fragments),
        technique_fragments=format_number(user.technique_fragments),
        genius_fragments=format_number(user.genius_fragments),
    )
    access = await get_intel_access(session, user_id)
    return text, development_menu([[bloodline_button(), awakening_button()], [technique_button(), path_button()]] + intel_entry_rows(scout_or_logs=bool(access.scout or access.logs), marks=bool(access.marks)))
