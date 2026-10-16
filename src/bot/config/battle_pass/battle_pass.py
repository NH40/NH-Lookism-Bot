"""Battle Pass (конфиг). Механика — как в Universe Anime Planet (две ветки, клейм любой ячейки
или «всё», дневной буст), но уровень растёт от ОПЫТА за выполненные ежедневные задания
(пользователь 2026-10-04). Сезоны по 30 дней, платная ветка — на сезон (донат, позже).
Награды и числа — решение автора кода, в рамках экономики LBP 2.0.
"""
from __future__ import annotations

from bot.constant.resource import (
    RES_BLOOD,
    RES_COINS,
    RES_DEV_POINTS,
    RES_GENIUS_FRAGMENTS,
    RES_PATH_FRAGMENTS,
    RES_PATH_POINTS,
    RES_TECHNIQUE_FRAGMENTS,
    RES_TICKETS,
)

BP_SEASON_DAYS = 30
BP_LEVEL_XP = 200  # опыт на уровень, плоско
# Как в UAP — 500 уровней с полной раскладкой; дальше бесконечно повторяется блок из 10 ценных
# уровней (пользователь 2026-10-08, AskUserQuestion: «цикл из 10 уровней»).
BP_MAIN_LEVELS = 500
BP_LOOP_LEVELS = 10
# Поощрение (пользователь): первое выполненное за день задание даёт опыт ×3, второе ×2…
BP_QUEST_ORDER_MULTIPLIERS: tuple[int, ...] = (3, 2)
# …и первые уровни за день — ×4 к опыту («первые 5–10 уровней»).
BP_BOOST_LEVELS = 8
BP_BOOST_MULTIPLIER = 4
# Все 10 заданий дня — бонус опыта (как «Мастер на все руки» в LBP1).
BP_ALL_DONE_XP = 150
# Темп: ~550 опыта заданий в день без поощрений → с поощрениями ~9 уровней в день → ~260 за
# сезон у того, кто выполняет все задания; 500 и цикл — для самых активных.

# Платная ветка — на текущий сезон, за донат-коины (не входит в 100 000 «купить всё» чёрного
# рынка: покупается каждый сезон заново).
BP_PREMIUM_PRICE = 299

BP_LEVELS_PER_PAGE = 5  # в боте — 2 строки по 5 ячеек (как в UAP)

# Свиток пропуска — отдельный предмет (`users.skip_scrolls`): мгновенно выполняет активное
# задание развития (пользователь: «пропустить задание на подтверждение убеждений для пути и
# тому подобное»).
ITEM_SCROLL = "scroll"

_FRAGMENTS = (RES_PATH_FRAGMENTS, RES_TECHNIQUE_FRAGMENTS, RES_GENIUS_FRAGMENTS)


def _base(level: int) -> dict[str, int]:
    """Награда бесплатной ветки за уровень (до премиум-надбавок)."""
    reward: dict[str, int] = {}
    if level % 250 == 0:  # пользователь: «за каждый 250-й уровень — каплю крови»
        reward[RES_BLOOD] = 1
        reward[RES_COINS] = 20_000
    elif level % 100 == 0:
        reward[ITEM_SCROLL] = 1
        reward[RES_TICKETS] = 5
    elif level % 10 == 0:
        reward[RES_TICKETS] = 2
        reward[_FRAGMENTS[(level // 10) % 3]] = 8
    else:
        step = level % 5
        if step == 1:
            reward[RES_COINS] = 2_000
        elif step == 2:
            reward[_FRAGMENTS[level % 3]] = 3
        elif step == 3:
            reward[RES_TICKETS] = 1
        elif step == 4:
            reward[RES_DEV_POINTS] = 2
        else:
            reward[RES_COINS] = 3_500
    return reward


def _loop(pos: int) -> dict[str, int]:
    """Награда позиции 1–10 в цикле после 500-го уровня: фрагменты, тикеты, очки развития,
    в конце блока — свиток. Капли крови в цикле нет — она только на 250-м и 500-м."""
    if pos == BP_LOOP_LEVELS:
        return {ITEM_SCROLL: 1, RES_TICKETS: 3}
    if pos % 2:
        return {_FRAGMENTS[(pos // 2) % 3]: 10}
    return {RES_TICKETS: 2} if pos % 4 == 2 else {RES_DEV_POINTS: 5}


def loop_position(level: int) -> int:
    """0 — уровень из основных 500; иначе позиция 1–10 в повторяющемся блоке."""
    return 0 if level <= BP_MAIN_LEVELS else (level - BP_MAIN_LEVELS - 1) % BP_LOOP_LEVELS + 1


def free_reward(level: int) -> dict[str, int]:
    pos = loop_position(level)
    return _loop(pos) if pos else _base(level)


def premium_reward(level: int) -> dict[str, int]:
    """Платная ветка: та же раскладка вдвое щедрее + свой бонус (очки пути, свитки, кровь)."""
    pos = loop_position(level)
    if pos:
        reward = {k: v * 2 for k, v in _loop(pos).items() if k != ITEM_SCROLL}
        reward[ITEM_SCROLL] = 1 if pos in (5, BP_LOOP_LEVELS) else 0
        reward[RES_PATH_POINTS] = 20
        return {k: v for k, v in reward.items() if v}
    reward = {k: v * 2 for k, v in _base(level).items() if k != ITEM_SCROLL}
    if level % 250 == 0:
        reward[RES_COINS] = 50_000
    if level % 50 == 0:  # свиток — раз в 50 уровней (в бесплатной — раз в 100)
        reward[ITEM_SCROLL] = 1
    if level % 5 == 0:
        reward[RES_PATH_POINTS] = reward.get(RES_PATH_POINTS, 0) + 20
    return reward


def level_from_xp(xp: int) -> int:
    return xp // BP_LEVEL_XP
