"""Картинки игры для Mini App: уменьшенное WebP-превью файла из `assets/` (оригиналы ~2,5 МБ
PNG — для мобильного WebView слишком тяжело). Превью нужной ширины генерируется один раз
(Pillow в потоке — не блокирует event loop) и кэшируется на диске; браузеру — долгий кэш.
Без авторизации: картинки публичные (карточки, боссы), а `<img>` не умеет слать заголовок
initData."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/img", tags=["img"])

ASSETS_DIR = Path(os.environ.get("ASSETS_DIR", "/app/assets")).resolve()
THUMBS_DIR = Path(os.environ.get("THUMBS_DIR", "/app/thumbs")).resolve()
_WIDTHS = (160, 320, 480, 720)  # фиксированный набор — нельзя забить диск произвольными размерами
_CACHE = {"Cache-Control": "public, max-age=2592000, immutable"}


def _make_thumb(source: Path, target: Path, width: int) -> None:
    from PIL import Image

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        img = img.convert("RGBA") if img.mode in ("P", "LA") else img
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        tmp = target.with_suffix(".tmp")
        img.save(tmp, "WEBP", quality=82, method=4)
        tmp.replace(target)


@router.get("/{path:path}")
async def get_image(path: str, w: int = Query(480)) -> FileResponse:
    width = min(_WIDTHS, key=lambda x: abs(x - w))
    source = (ASSETS_DIR / path).resolve()
    if not source.is_relative_to(ASSETS_DIR) or source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(404, "Not found")
    if not source.is_file():
        raise HTTPException(404, "Not found")
    target = THUMBS_DIR / str(width) / Path(path).with_suffix(".webp")
    if not target.is_file() or target.stat().st_mtime < source.stat().st_mtime:
        await asyncio.to_thread(_make_thumb, source, target, width)
    return FileResponse(target, media_type="image/webp", headers=_CACHE)
