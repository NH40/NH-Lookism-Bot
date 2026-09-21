"""Единая схема ключей Redis — чтобы не разбредались по хендлерам/сервисам (тот же
принцип, что в Universe Anime Planet).

Доменные ключи (лидерборды king_bot/emperor/gang, кэш file_id карточек и т.п.)
добавляются сюда по мере переноса соответствующего домена, а не заводятся ad-hoc
строками прямо в хендлере/сервисе.
"""
from __future__ import annotations


def action_lock(user_id: int, action: str) -> str:
    """Антидубликат-лок на время обработки одного действия (SET NX PX, правило 2)."""
    return f"lock:{user_id}:{action}"


def tech_mode_flag() -> str:
    return "flag:tech_mode"


def throttle_flag(user_id: int) -> str:
    """Общий антифлуд (см. middlewares/throttling.py) — не путать с action_lock: тот
    защищает конкретное resource-affecting действие от повторного клика (правило 2),
    этот — общий предохранитель от спама любыми апдейтами одного игрока подряд."""
    return f"throttle:{user_id}"


def recruit_extra_cooldown(user_id: int) -> str:
    """КД вербовки статистов (20 минут, raw-notes «Карта») — сам ключ И есть КД
    (`SET NX EX`, правило 4: горячее состояние в Redis, не Postgres-колонка), TTL
    одновременно и защищает от повторного клика (правило 2), и реализует саму игровую
    механику ожидания — второй Redis-лок сверху не нужен."""
    return f"cooldown:recruit_extra:{user_id}"


def train_extras_cooldown(user_id: int) -> str:
    """КД тренировки статистов (30 минут, raw-notes «Карта») — тот же приём, что
    `recruit_extra_cooldown`."""
    return f"cooldown:train_extras:{user_id}"
