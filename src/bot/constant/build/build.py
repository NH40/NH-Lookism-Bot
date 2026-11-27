"""Build — источники бафов (константы). Ключи `BattleBuild.by_source` и
`copy_sources` (родословная Джинена копирует конкретный источник противника)."""
from __future__ import annotations

SOURCE_BLOODLINE = "bloodline"
SOURCE_PATH = "path"
SOURCE_TECHNIQUE = "technique"
SOURCE_GENIUS = "genius"
SOURCE_PATH2 = "path2"  # второе тело (донат)
SOURCE_BLOODLINE2 = "bloodline2"
SOURCE_MASTERY = "mastery"  # пассивы изученных техник мастерства (2026-11-23)
# Режимы автоматики Ямадзаки для `get_combat_profile(auto=...)` — у вербовки и тренировок разные бонусы.
AUTO_RECRUIT = "recruit"
AUTO_TRAIN = "train"
SOURCES: tuple[str, ...] = (SOURCE_BLOODLINE, SOURCE_PATH, SOURCE_TECHNIQUE, SOURCE_GENIUS)
