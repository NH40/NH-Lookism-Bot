"""Журнал действий и разведка (конфиг)."""
from __future__ import annotations

from bot.constant.activity import ACT_BATTLE, ACT_BUSINESS, ACT_CAPTURE, ACT_DEVELOPMENT

ACTIVITY_KEEP_DAYS = 7
# Наблюдение по уровням: 1 — бои, 2 — + захваты и бизнес, 3 — всё, включая развитие.
LOG_KINDS_BY_LEVEL: dict[int, tuple[str, ...]] = {
    1: (ACT_BATTLE,),
    2: (ACT_BATTLE, ACT_CAPTURE, ACT_BUSINESS),
    3: (ACT_BATTLE, ACT_CAPTURE, ACT_BUSINESS, ACT_DEVELOPMENT),
}
LOG_ENTRIES_BY_LEVEL: dict[int, int] = {1: 5, 2: 10, 3: 20}
MARK_FEED_ENTRIES = 3  # последних событий каждого помеченного игрока на экране меток
