"""Арт событий карты (боссы, учителя) для бота — та же логика, что `api/routers/map.event_art`:
выделенный файл в `assets/<папка>/` по коду или алиасу (`config/event.ART_ALIASES`), иначе
подставной портрет из конфига, иначе None."""
from __future__ import annotations

from pathlib import Path

from bot.config.card import ASSETS_DIR
from bot.config.event.art import ART_ALIASES, BOSS_ART, SCHOOL_TEACHER_ART, TECHNIQUE_TEACHER_ART
from bot.constant.event import EVENT_BOSS, EVENT_SCHOOL_TEACHER, EVENT_TEACHER

_SOURCES: dict[str, tuple[str, dict[str, str | None]]] = {
    EVENT_BOSS: ("boss", BOSS_ART),
    EVENT_TEACHER: ("teacher_ut", TECHNIQUE_TEACHER_ART),
    EVENT_SCHOOL_TEACHER: ("teacher_statist", SCHOOL_TEACHER_ART),
}
_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def event_art_path(kind: str, code: str) -> Path | None:
    source = _SOURCES.get(kind)
    if source is None:
        return None
    folder_name, fallback = source
    folder = ASSETS_DIR / folder_name
    if folder.is_dir():
        names = {code.lower(), *(a.lower() for a in ART_ALIASES.get(code, ()))}
        for f in folder.iterdir():
            if f.is_file() and f.stem.lower() in names and f.suffix.lower() in _EXTS:
                return f
    rel = fallback.get(code)
    path = ASSETS_DIR / rel if rel else None
    return path if path is not None and path.is_file() else None
