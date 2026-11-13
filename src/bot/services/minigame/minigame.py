"""Мини-игры занятий техники и финала мастерства (сервис, пользователь 2026-11-13).

Контекст игры — строка: `t:<код техники>` (этапы оплаченного занятия на следующий уровень) или
`m:<мастерство>` (одна из 4 игр вместо Тома Ли). `start` выдаёт токен и параметры (Redis, TTL),
`finish` проверяет время и счёт и засчитывает: этап занятия — прогресс квеста `QUEST_TECH_LEVEL`
(задание `TASK_MINIGAME`, этапы по порядку, провал переигрывается бесплатно), игра мастерства —
+1 очко, все 4 — этап закрыт (как раньше победа над Томом).
"""
from __future__ import annotations

import json
import math
import secrets
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.minigame import (
    MASTERY_GAMES,
    MASTERY_HIT_SHARE,
    MASTERY_MISS_MAX,
    MASTERY_MISS_MIN,
    MASTERY_POWER_PER_TAP,
    MASTERY_STRENGTH_SECONDS,
    MASTERY_STRIKES,
    MASTERY_TAPS_MAX,
    MASTERY_TAPS_MIN,
    MIN_TIME_SHARE,
    STAGES_PER_LEVEL,
    TOKEN_TTL_SECONDS,
    difficulty_for_level,
    difficulty_for_stage,
    params,
    tech_stages,
)
from bot.constant.characteristic import MASTERIES, MASTERY_ENDURANCE, MASTERY_STRENGTH
from bot.constant.dev_quest import QUEST_TECH_LEVEL, TASK_MINIGAME

CTX_TECH, CTX_MASTERY = "t", "m"


class MinigameError(Exception):
    """`code`: unknown, no_lesson, locked, done, expired, too_fast, failed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Stage:
    game: str
    done: bool
    playable: bool


@dataclass(frozen=True, slots=True)
class Board:
    ctx: str
    title_code: str  # код техники или мастерства — для заголовка
    level: int  # уровень техники / этап мастерства
    stages: tuple[Stage, ...]


def _key(token: str) -> str:
    return f"mg:{token}"


# --- состояние ---


async def _tech_quest(session: AsyncSession, user_id: int, code: str, *, for_update: bool = False):
    from bot.db.repositories import dev_quest as dq_repo
    from bot.services.unique_technique import get_training

    row = await get_training(session, user_id, code)
    if row.next_level is None or row.quest is None or TASK_MINIGAME not in row.quest.tasks:
        raise MinigameError("no_lesson")
    quest = await dq_repo.get_active_for_update(session, user_id, QUEST_TECH_LEVEL, row.quest.ref) if for_update else None
    return row, quest


async def _mastery_quest(session: AsyncSession, user_id: int, *, for_update: bool = False):
    from bot.services.mastery import lock_quest_for_tom
    from bot.services.mastery.mastery import QuestNotActiveError, TomLockedError

    try:
        return await lock_quest_for_tom(session, user_id) if for_update else await _mastery_peek(session, user_id)
    except (QuestNotActiveError, TomLockedError) as exc:
        raise MinigameError("locked") from exc


async def _mastery_peek(session: AsyncSession, user_id: int):
    from bot.db.repositories import mastery as mastery_repo
    from bot.services.mastery.mastery import QUEST_ACTIVE, QuestNotActiveError, TomLockedError, _tom_unlocked

    quest = await mastery_repo.get(session, user_id)
    if quest is None or quest.status != QUEST_ACTIVE:
        raise QuestNotActiveError
    if not _tom_unlocked(quest):
        raise TomLockedError
    return quest


async def board(session: AsyncSession, user_id: int, ctx: str) -> Board:
    kind, _, code = ctx.partition(":")
    if kind == CTX_TECH:
        row, _ = await _tech_quest(session, user_id, code)
        done = row.quest.progress.get(TASK_MINIGAME, 0)
        games = tech_stages(code, row.next_level)
        stages = tuple(Stage(g, i < done, i == done) for i, g in enumerate(games))
        return Board(ctx, code, row.next_level, stages)
    if kind == CTX_MASTERY:
        quest = await _mastery_quest(session, user_id)
        mask = quest.games_done
        stages = tuple(Stage(MASTERY_GAMES[m], bool(mask & (1 << i)), not mask & (1 << i)) for i, m in enumerate(MASTERIES))
        return Board(ctx, code, quest.stage, stages)
    raise MinigameError("unknown")


# --- параметры игры ---


async def _mastery_params(session: AsyncSession, user_id: int, mastery: str, quest) -> dict:
    from bot.services.extra import get_army_stats

    d = difficulty_for_stage(quest.stage)
    army = max(1, (await get_army_stats(session, user_id)).total_power)
    target = max(1, quest.tom_power)
    if mastery == MASTERY_STRENGTH:  # шквал: каждое нажатие — доля мощи армии, набить мощь Тома
        taps = min(MASTERY_TAPS_MAX, max(MASTERY_TAPS_MIN, math.ceil(target / (army * MASTERY_POWER_PER_TAP))))
        return {"seconds": MASTERY_STRENGTH_SECONDS, "need": taps, "max_score": MASTERY_STRENGTH_SECONDS * 16,
                "army_power": army, "target_power": target}
    if mastery == MASTERY_ENDURANCE:  # блоки: пропущенный удар снимает долю мощи Тома с армии
        miss = min(MASTERY_MISS_MAX, max(MASTERY_MISS_MIN, int((army - 1) // max(1, target * MASTERY_HIT_SHARE))))
        p = params(MASTERY_GAMES[mastery], d)
        warn = p["warn_ms"]
        return {"strikes": MASTERY_STRIKES, "warn_ms": warn, "max_miss": miss, "need": MASTERY_STRIKES - miss,
                "max_score": MASTERY_STRIKES, "seconds": MASTERY_STRIKES * (warn + 300) / 1000,
                "army_power": army, "target_power": target}
    return params(MASTERY_GAMES[mastery], d)


async def start(session: AsyncSession, redis: Redis, user_id: int, ctx: str, stage: int) -> dict:
    """Начать этап `stage` (0-based) — токен на `TOKEN_TTL_SECONDS` и параметры игры."""
    b = await board(session, user_id, ctx)
    if not 0 <= stage < len(b.stages):
        raise MinigameError("unknown")
    s = b.stages[stage]
    if s.done:
        raise MinigameError("done")
    if not s.playable:
        raise MinigameError("locked")
    kind, _, code = ctx.partition(":")
    if kind == CTX_TECH:
        p = params(s.game, difficulty_for_level(b.level))
    else:
        p = await _mastery_params(session, user_id, MASTERIES[stage], await _mastery_peek(session, user_id))
    token = secrets.token_urlsafe(16)
    await redis.set(_key(token), json.dumps({"u": user_id, "ctx": ctx, "stage": stage, "game": s.game, "p": p, "t": time.time()}),
                    ex=TOKEN_TTL_SECONDS)
    return {"token": token, "game": s.game, "params": p}


async def finish(session: AsyncSession, redis: Redis, user_id: int, token: str, score: int) -> Board:
    """Результат этапа: проверка времени и счёта → засчитать. Провал — токен сгорает, этап можно
    начать заново. Коммитит."""
    raw = await redis.getdel(_key(token))
    if raw is None:
        raise MinigameError("expired")
    data = json.loads(raw)
    if data["u"] != user_id:
        raise MinigameError("expired")
    p = data["p"]
    if time.time() - data["t"] < p.get("seconds", 0) * MIN_TIME_SHARE:
        raise MinigameError("too_fast")
    if not p["need"] <= score <= p["max_score"]:
        raise MinigameError("failed")
    ctx, stage = data["ctx"], data["stage"]
    kind, _, code = ctx.partition(":")
    if kind == CTX_TECH:
        row, quest = await _tech_quest(session, user_id, code, for_update=True)
        done = int((quest.progress or {}).get(TASK_MINIGAME, 0)) if quest is not None else STAGES_PER_LEVEL
        if quest is None or done != stage:
            raise MinigameError("done")
        quest.progress = {**(quest.progress or {}), TASK_MINIGAME: done + 1}
    else:
        quest = await _mastery_quest(session, user_id, for_update=True)
        bit = 1 << stage
        if quest.games_done & bit:
            raise MinigameError("done")
        from bot.services.mastery.mastery import grant_game_point

        grant_game_point(quest, bit)
    await session.commit()
    return await board(session, user_id, ctx) if kind == CTX_TECH or not _all_done(quest) else Board(ctx, code, quest.stage, ())


def _all_done(quest) -> bool:
    return quest.games_done == (1 << len(MASTERIES)) - 1
