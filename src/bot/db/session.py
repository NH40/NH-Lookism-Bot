from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import TextClause, event
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bot.config.settings import Settings
from bot.config.admin import LOG_SLOW_SQL_MS
from bot.services.error_log import normalize, record_slow
from bot.utils.log_context import forget_tag, forget_tag_on_checkin, tag_ledger_writes


_MEMO_KEYS = ("build_memo",)


def _clear_memo(session: Session, *args) -> None:
    for key in _MEMO_KEYS:
        session.info.pop(key, None)


def _clear_memo_on_write(state) -> None:
    """Запомненное на сессию живёт только между записями: чтение его не сбрасывает, любой другой запрос — да."""
    statement = state.statement
    if state.is_select or (isinstance(statement, TextClause) and statement.text.lstrip()[:6].upper() == "SELECT"):
        return
    _clear_memo(state.session)


event.listen(Session, "do_orm_execute", _clear_memo_on_write)
event.listen(Session, "after_flush", _clear_memo)
event.listen(Session, "after_commit", _clear_memo)
event.listen(Session, "after_rollback", _clear_memo)


def _sql_started(conn, cursor, statement, parameters, context, executemany) -> None:
    context._log_started = time.perf_counter()


def _sql_finished(conn, cursor, statement, parameters, context, executemany) -> None:
    ms = int((time.perf_counter() - context._log_started) * 1000)
    if ms >= LOG_SLOW_SQL_MS:
        record_slow("sql", normalize(" ".join(statement.split()))[:200], ms)


def make_engine(settings: Settings) -> AsyncEngine:
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    event.listen(engine.sync_engine, "before_cursor_execute", tag_ledger_writes)
    event.listen(engine.sync_engine, "before_cursor_execute", _sql_started)
    event.listen(engine.sync_engine, "after_cursor_execute", _sql_finished)
    event.listen(engine.sync_engine, "commit", forget_tag)
    event.listen(engine.sync_engine, "rollback", forget_tag)
    event.listen(engine.sync_engine.pool, "checkin", forget_tag_on_checkin)
    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Транзакция на весь блок: commit при успехе, rollback при исключении."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
