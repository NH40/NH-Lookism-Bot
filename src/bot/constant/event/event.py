"""События на карте — боссы и учителя (константы). Дизайн —
`docs/design/development_systems.md`, «Боссы на карте» и «Архитектура реализации»."""
from __future__ import annotations

EVENT_BOSS = "boss"
EVENT_TEACHER = "teacher"
EVENT_SCHOOL_TEACHER = "school"  # учитель статистов (Хансу, Элита, Бэкхо, Том Ли), code — школа

# Боссы-источники фрагментов (пользователь): Ким Гапрен → пути, Джинен → УТ, Элита → гениальность.
BOSS_GAPRYONG = "gapryong"
BOSS_JINYEONG = "jinyeong"
BOSS_ELITE = "elite"
BOSSES: tuple[str, ...] = (BOSS_GAPRYONG, BOSS_JINYEONG, BOSS_ELITE)

# Что падает с босса — колонка-валюта `users`.
FRAGMENT_PATH = "path_fragments"
FRAGMENT_TECHNIQUE = "technique_fragments"
FRAGMENT_GENIUS = "genius_fragments"
BOSS_FRAGMENT: dict[str, str] = {
    BOSS_GAPRYONG: FRAGMENT_PATH,
    BOSS_JINYEONG: FRAGMENT_TECHNIQUE,
    BOSS_ELITE: FRAGMENT_GENIUS,
}

CB_EVENT_VIEW_PREFIX = "event:view:"
"""f"{CB_EVENT_VIEW_PREFIX}{event_id}"."""
CB_EVENT_FIGHT_PREFIX = "event:fight:"
"""f"{CB_EVENT_FIGHT_PREFIX}{event_id}" — бой с боссом."""
CB_EVENT_CONNECT_PREFIX = "event:connect:"
"""f"{CB_EVENT_CONNECT_PREFIX}{event_id}" — законнектиться с учителем."""
