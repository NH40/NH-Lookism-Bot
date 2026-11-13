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
    images: list[str] = []  # пути в assets/ (через /api/img) — листы систем развития


# Листы систем развития (`assets/guide`, собраны из конфига игры) — только в Mini App.
_IMAGE_SECTIONS = (
    ("g_bloodlines", "🩸 Родословные", "bloodlines", "Все родословные по уровням — что даёт каждый уровень и итог на 10-м."),
    ("g_paths", "🛤 Пути", "paths", "Все пути по уровням, их шкалы и что даёт шкала."),
    ("g_techniques", "🥋 Техники", "techniques", "Все уникальные техники по уровням и их учителя."),
    ("g_genius", "🧠 Гениальность", "genius", "Все гениальности по уровням."),
)


def _images(prefix: str) -> list[str]:
    from api.routers.img import ASSETS_DIR

    folder = ASSETS_DIR / "guide"
    files = sorted(folder.glob(f"{prefix}-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1])) if folder.is_dir() else []
    return [f"guide/{p.name}" for p in files]


class GuideOut(BaseModel):
    sections: list[GuideSectionOut]


@router.get("", response_model=GuideOut)
async def get_guide(_user_id: int = Depends(get_current_user_id)) -> GuideOut:
    sections = [GuideSectionOut(code=c, title=clean_label(t), body=b) for c, t, b in HELP_SECTIONS]
    sections += [GuideSectionOut(code=c, title=clean_label(t), body=b, images=_images(p)) for c, t, p, b in _IMAGE_SECTIONS]
    return GuideOut(sections=sections)
