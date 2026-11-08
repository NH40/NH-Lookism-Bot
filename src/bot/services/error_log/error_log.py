"""Журнал ошибок и медленных операций: то, что раньше жило только в логах Docker и быстро затиралось.

Одинаковые ошибки схлопываются в одну строку со счётчиком (`fingerprint`). Запись идёт в фоне: обработчик
логов только кладёт запись в очередь в памяти и никогда не ждёт базу, поэтому логирование не тормозит игру,
а упавшая база не ломает логирование. О новом виде ошибки приходит пуш супер-админам, не больше
`ERROR_ALERTS_PER_HOUR` в час."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
import traceback
from collections import deque
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.admin import ERROR_ALERTS_PER_HOUR
from bot.constant.ledger import LOG_KIND_ERROR, LOG_KIND_SLOW
from bot.utils.log_context import current

_SINK_LOGGER = "bot.error_sink"
log = logging.getLogger(_SINK_LOGGER)

FLUSH_SECONDS = 5
_MAX_DETAIL = 6000
_DIGITS = re.compile(r"\d+")
# Эти записи дублируют то, что уже записано с контекстом игрока (`LogContextMiddleware`, ASGI-обёртка API).
_DUPLICATES = (("aiogram.event", "Cause exception"), ("uvicorn.error", "Exception in ASGI"))

_queue: deque["Entry"] = deque(maxlen=2000)


@dataclass(slots=True)
class Entry:
    kind: str
    process: str
    fingerprint: str
    title: str
    detail: str
    user_id: int | None
    source: str
    ms: int = 0
    hits: int = 1


def normalize(value: str) -> str:
    """Числа в подписи не должны плодить отдельные строки журнала: `travel:go:12` → `travel:go:#`."""
    return _DIGITS.sub("#", value)


def _hash(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:24]


def record_slow(process: str, where: str, ms: int) -> None:
    user_id, source = current()
    _queue.append(Entry(LOG_KIND_SLOW, process, _hash(LOG_KIND_SLOW, process, where), where[:256], "", user_id, source, ms))


def _own_frame(tb) -> str:
    """Самое глубокое место в коде игры — по нему ошибки считаются одинаковыми."""
    found = ""
    for frame in traceback.extract_tb(tb):
        if "/bot/" in frame.filename or "/api/" in frame.filename or "\\bot\\" in frame.filename:
            found = f"{os.path.basename(frame.filename)}:{frame.name}"
    return found


class DbErrorHandler(logging.Handler):
    """Складывает ошибки из логов в очередь журнала."""

    def __init__(self, process: str) -> None:
        super().__init__(logging.ERROR)
        self.process = process

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.name == _SINK_LOGGER or any(record.name == n and message.startswith(p) for n, p in _DUPLICATES):
                return
            user_id, source = current()
            if record.exc_info and record.exc_info[0]:
                kind, value, tb = record.exc_info
                title = f"{kind.__name__}: {value}"
                where = _own_frame(tb)
                fingerprint = _hash(LOG_KIND_ERROR, kind.__name__, where or normalize(str(value))[:120])
                detail = f"{message}\n" + "".join(traceback.format_exception(kind, value, tb))
            else:
                title = message
                fingerprint = _hash(LOG_KIND_ERROR, record.name, normalize(message)[:120])
                detail = f"{record.name}\n{message}"
            _queue.append(Entry(LOG_KIND_ERROR, self.process, fingerprint, title[:256], detail[-_MAX_DETAIL:], user_id, source))
        except Exception:  # noqa: BLE001 — логирование не должно ронять игру
            self.handleError(record)


_UPSERT = text("""
    INSERT INTO error_log (fingerprint, kind, process, title, detail, user_id, source, hits, max_ms)
    VALUES (:fingerprint, :kind, :process, :title, :detail, :user_id, :source, :hits, :ms)
    ON CONFLICT (fingerprint) DO UPDATE SET
        hits = error_log.hits + EXCLUDED.hits, max_ms = GREATEST(error_log.max_ms, EXCLUDED.max_ms), last_seen = now(),
        title = EXCLUDED.title, detail = EXCLUDED.detail, user_id = EXCLUDED.user_id, source = EXCLUDED.source, process = EXCLUDED.process
    RETURNING (xmax = 0)
""")


async def flush(session_factory: async_sessionmaker[AsyncSession]) -> list[Entry]:
    """Записать накопленное. → новые виды ошибок (для пуша). Одинаковые за проход складываются."""
    grouped: dict[str, Entry] = {}
    while _queue:
        entry = _queue.popleft()
        seen = grouped.get(entry.fingerprint)
        if seen is None:
            grouped[entry.fingerprint] = entry
        else:
            seen.hits += 1
            seen.ms = max(seen.ms, entry.ms)
    if not grouped:
        return []
    fresh = []
    async with session_factory() as session:
        for e in grouped.values():
            inserted = await session.scalar(_UPSERT, {
                "fingerprint": e.fingerprint, "kind": e.kind, "process": e.process, "title": e.title, "detail": e.detail,
                "user_id": e.user_id, "source": e.source, "hits": e.hits, "ms": e.ms,
            })
            if inserted and e.kind == LOG_KIND_ERROR:
                fresh.append(e)
        await session.commit()
    return fresh


async def run_sink(session_factory: async_sessionmaker[AsyncSession], get_bot=None) -> None:
    """Фоновая запись журнала; `get_bot` — чем слать пуш о новой ошибке."""
    from bot.config.settings import get_settings
    from bot.texts.admin.logs import error_alert
    from bot.utils.notify import notify

    sent: deque[float] = deque()
    while True:
        await asyncio.sleep(FLUSH_SECONDS)
        try:
            fresh = await flush(session_factory)
        except Exception:  # noqa: BLE001 — база недоступна: запись просто потеряется
            log.warning("Не удалось записать журнал ошибок", exc_info=True)
            continue
        if get_bot is None or not fresh:
            continue
        now = time.monotonic()
        while sent and now - sent[0] > 3600:
            sent.popleft()
        for entry in fresh:
            if len(sent) >= ERROR_ALERTS_PER_HOUR:
                break
            sent.append(now)
            for admin_id in get_settings().admin_ids:
                await notify(get_bot(), admin_id, error_alert(entry))
