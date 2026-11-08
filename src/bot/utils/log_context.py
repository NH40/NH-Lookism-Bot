"""Контекст текущего действия для журналов: откуда пришло (кнопка, команда, запрос Mini App), кто и почему.

Журнал имущества `player_ledger` пишут триггеры Postgres, поэтому в него попадает любое изменение, даже из
места, про которое забыли. Источник и причину триггер читает из настроек транзакции: их ставит
`tag_ledger_writes` перед запросом, который может что-то изменить в отслеживаемых данных, и только если
значения поменялись. Обычные чтения и `UPDATE users SET last_active_at` лишнего похода в базу не делают."""
from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_source: ContextVar[str] = ContextVar("log_source", default="system")
_reason: ContextVar[str] = ContextVar("log_reason", default="")
_user: ContextVar[int | None] = ContextVar("log_user", default=None)

_SET_SQL = "SELECT set_config('app.log_src', $1, true), set_config('app.log_reason', $2, true)"
_TAG_KEY = "ledger_tag"
_WATCH = re.compile(
    r"coins|tickets_count|_points|fragments|blood_drops|skip_scrolls|phase|city_id|potential|bloodline|active_(?:path|technique|genius)"
    r"|awakening|is_banned|admin_role|second_body|stat_|mastery_|business_|path_stage|quantity|owner_id|businesses"
)


def set_source(value: str) -> Token:
    return _source.set(value[:64])


def reset_source(token: Token) -> None:
    _source.reset(token)


def set_user(user_id: int | None) -> Token:
    return _user.set(user_id)


def reset_user(token: Token) -> None:
    _user.reset(token)


def current() -> tuple[int | None, str]:
    """(игрок, источник) текущего действия — для технических логов."""
    return _user.get(), _source.get()


def current_source() -> str:
    return _source.get()


@contextmanager
def coin_reason(reason: str) -> Iterator[None]:
    """Причина изменения там, где источник сам ничего не скажет (Менеджер, Элита, кража и т.п.)."""
    token = _reason.set(reason)
    try:
        yield
    finally:
        _reason.reset(token)


def tag_ledger_writes(conn, cursor, statement, parameters, context, executemany) -> None:
    """`before_cursor_execute`: передать контекст триггерам журнала."""
    if statement.lstrip()[:6].upper() == "SELECT" or not _WATCH.search(statement):
        return
    value = (_source.get(), _reason.get())
    if conn.info.get(_TAG_KEY) == value:
        return
    cursor.execute(_SET_SQL, value)
    conn.info[_TAG_KEY] = value


def forget_tag(conn) -> None:
    """Конец транзакции: настройки `set_config(..., true)` сброшены, ставить заново."""
    conn.info.pop(_TAG_KEY, None)


def forget_tag_on_checkin(dbapi_connection, record) -> None:
    record.info.pop(_TAG_KEY, None)
