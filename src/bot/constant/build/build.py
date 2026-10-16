"""Build — источники бафов (константы). Ключи `BattleBuild.by_source` и
`copy_sources` (родословная Джинена копирует конкретный источник противника)."""
from __future__ import annotations

SOURCE_BLOODLINE = "bloodline"
SOURCE_PATH = "path"
SOURCE_TECHNIQUE = "technique"
SOURCE_GENIUS = "genius"
SOURCE_PATH2 = "path2"  # второе тело (донат)
SOURCE_BLOODLINE2 = "bloodline2"
SOURCES: tuple[str, ...] = (SOURCE_BLOODLINE, SOURCE_PATH, SOURCE_TECHNIQUE, SOURCE_GENIUS)
