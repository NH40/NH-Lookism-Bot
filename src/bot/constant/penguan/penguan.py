"""Родословная Пеньгуана (константы): callback'и экранов и виды временных бафов."""
from __future__ import annotations

BUFF_BRIBE = "bribe"  # Подкуп: реакции врага слабее
BUFF_CHEST = "chest"  # Военная казна: +атака
BUFF_RECRUIT = "recruit"  # Золотая вербовка: больше бойцов за вербовку
BUFFS: tuple[str, ...] = (BUFF_BRIBE, BUFF_CHEST, BUFF_RECRUIT)

CB_PG_OPEN = "pg:open"
CB_PG_BUFF_PREFIX = "pg:buff:"  # f"{CB_PG_BUFF_PREFIX}{kind}"
CB_PG_BUILDER = "pg:builder"
CB_PG_SET_PREFIX = "pg:set:"  # f"{CB_PG_SET_PREFIX}{param}:{delta}" — шаг конструктора
CB_PG_BUY_PREFIX = "pg:buy:"  # f"{CB_PG_BUY_PREFIX}{quantity}"
CB_PG_BUYBACK = "pg:buyback"
CB_PG_BUYOUT = "pg:buyout"

# Параметры конструктора статистов (часть `CB_PG_SET_PREFIX`).
P_RANK, P_LEVEL, P_STARS, P_SCHOOL, P_SCHOOL_LEVEL = "rank", "level", "stars", "school", "slevel"


# Ключи Redis.
def key_builder(user_id: int) -> str:
    return f"pg:cfg:{user_id}"  # выбор в конструкторе статистов (JSON)


def key_day(user_id: int, day: str) -> str:
    return f"pg:day:{user_id}:{day}"  # hash: power — куплено мощи за сутки, count — покупок


def key_fallen(user_id: int) -> str:
    return f"pg:fallen:{user_id}"  # павшие последнего боя (JSON)


def key_buyout_cd(user_id: int) -> str:
    return f"pg:buyout:{user_id}"


def key_lock(user_id: int) -> str:
    return f"lock:pg:{user_id}"
