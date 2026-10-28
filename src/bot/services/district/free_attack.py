"""«Свободная атака» — бой без КД (сервис). Источники: Ловкость (+1% за ступень) и скиллы позиций
«Неудержимый» (победа) / «Двойной захват» (бой с ботами), не больше 50%. Баг 2026-10-28: шансы
складывались и не зависели от уже выпавших подряд, на высокой ловкости выходило до ~12 атак без КД.
Теперь каждая выпавшая подряд свободная атака умножает шанс следующей на
`FREE_ATTACK_CHAIN_DECAY` (40% → 20% → 10%…), первая атака с обычным КД сбрасывает цепочку.
"""
from __future__ import annotations

import random

from redis.asyncio import Redis

from bot.cache.keys import free_attack_chain
from bot.config.game import FREE_ATTACK_CHAIN_DECAY, FREE_ATTACK_CHAIN_TTL_SECONDS


def _chance(profile, *, won: bool, vs_bots: bool) -> float:
    """Шанс без учёта цепочки: Ловкость ИЛИ скиллы позиций (независимые броски, как было)."""
    agility = profile.free_attack_percent() / 100
    skills = 0.0
    if won and profile.build.positions is not None:
        pos = profile.build.positions
        skills = min(0.5, (pos.get("no_cd_bots") if vs_bots else 0.0) + pos.get("no_cd_on_win"))
    return 1 - (1 - min(1.0, agility)) * (1 - skills)


async def roll_free_attack(redis: Redis, user_id: int, profile, *, won: bool, vs_bots: bool) -> bool:
    """Бросок «бой без КД» с учётом цепочки. Обновляет счётчик цепочки (best-effort)."""
    key = free_attack_chain(user_id)
    try:
        chain = int(await redis.get(key) or 0)
    except Exception:  # noqa: BLE001 — сбой Redis не должен ломать бой; без цепочки — без бонуса
        chain = 99
    free = random.random() < _chance(profile, won=won, vs_bots=vs_bots) * FREE_ATTACK_CHAIN_DECAY ** chain
    try:
        if free:
            await redis.set(key, chain + 1, ex=FREE_ATTACK_CHAIN_TTL_SECONDS)
        else:
            await redis.delete(key)
    except Exception:  # noqa: BLE001
        pass
    return free
