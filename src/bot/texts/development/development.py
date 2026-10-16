"""Экран «📈 Развитие» — системы бафов билда (тексты). Дизайн — `docs/design/development_systems.md`."""
from __future__ import annotations

DEVELOPMENT_SCREEN = (
    "📈 <b>Развитие</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<i>Из этих систем ты собираешь свой билд.</i>\n\n"
    "{bloodline_line}\n"
    "{genius_line}\n"
    "{technique_line}\n"
    "{path_line}\n"
    "{awakening_line}\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🧩 Фрагменты: 🛤 {path_fragments} · 🥋 {technique_fragments} · 🧠 {genius_fragments}\n"
    "<i>Фрагменты падают с боссов на 🗺 Карте: Ким Гапрен — пути, Джинен — техники, Элита — гениальность.</i>"
)
TECHNIQUE_LINE_NONE = "🥋 <b>Уникальная техника:</b> найди учителя на 🗺 Карте"
PATH_LINE_NONE = "🛤 <b>Путь:</b> ещё не пробудился"
BTN_BACK_TO_DEVELOPMENT = "◀️ К развитию"
