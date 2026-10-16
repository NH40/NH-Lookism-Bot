"""Гайд в Mini App — те же разделы и тексты, что у /help бота (`texts/help.HELP_SECTIONS`).
Тело — HTML бота (<b>, <i>, переносы строк): тексты наши, не пользовательские."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import get_current_user_id
from api.routers._common import clean_label
from bot.texts.help import HELP_SECTIONS

router = APIRouter(prefix="/api/guide", tags=["guide"])


class GuideSectionOut(BaseModel):
    code: str
    title: str
    body: str


class GuideOut(BaseModel):
    sections: list[GuideSectionOut]


@router.get("", response_model=GuideOut)
async def get_guide(_user_id: int = Depends(get_current_user_id)) -> GuideOut:
    return GuideOut(sections=[GuideSectionOut(code=c, title=clean_label(t), body=b) for c, t, b in HELP_SECTIONS])
