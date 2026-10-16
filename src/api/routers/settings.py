"""API-роутер Mini App для домена settings: переключатели push-уведомлений.

Бизнес-логика — ТОЛЬКО через bot.services.settings (тот же сервис, что вызывает и
bot.handlers.settings)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.routers.profile import plain
from bot.constant.settings import NOTIFY_CATEGORIES
from bot.services.settings import UnknownCategoryError, muted_categories, set_all, toggle
from bot.texts.settings import NOTIFY_LABELS, NOTIFY_TOGGLED_OFF, NOTIFY_TOGGLED_ON

router = APIRouter(prefix="/api/settings", tags=["settings"])


class CategoryOut(BaseModel):
    code: str
    label: str
    enabled: bool


class SettingsOut(BaseModel):
    categories: list[CategoryOut]


class ToggleIn(BaseModel):
    category: str


class AllIn(BaseModel):
    enabled: bool


@router.get("", response_model=SettingsOut)
async def get_settings_screen(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> SettingsOut:
    muted = await muted_categories(session, user_id)
    return SettingsOut(
        categories=[
            CategoryOut(code=code, label=plain(NOTIFY_LABELS.get(code, code)), enabled=code not in muted)
            for code in NOTIFY_CATEGORIES
        ]
    )


@router.post("/toggle")
async def toggle_category(
    body: ToggleIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        enabled = await toggle(session, user_id, body.category)
    except UnknownCategoryError:
        raise HTTPException(400, "Неизвестная категория уведомлений.")
    label = plain(NOTIFY_LABELS.get(body.category, body.category))
    return {"message": (NOTIFY_TOGGLED_ON if enabled else NOTIFY_TOGGLED_OFF).format(label=label), "enabled": enabled}


@router.post("/all")
async def toggle_all(
    body: AllIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await set_all(session, user_id, body.enabled)
    return {"message": "Все уведомления включены." if body.enabled else "Все уведомления выключены."}
