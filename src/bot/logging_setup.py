from __future__ import annotations

import logging
import sys

from bot.services.error_log import DbErrorHandler
from bot.utils.log_context import current


class _ContextFilter(logging.Filter):
    """Добавляет к строке лога игрока и кнопку: `[123 cb:shop:buy]`."""

    def filter(self, record: logging.LogRecord) -> bool:
        user_id, source = current()
        record.ctx = f"[{user_id or '-'} {source}] " if user_id or source != "system" else ""
        return True


def setup_logging(level: str, process: str = "bot") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(ctx)s%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(_ContextFilter())
    root.handlers.clear()
    root.addHandler(handler)
    root.addHandler(DbErrorHandler(process))

    if level.upper() != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("aiogram").setLevel(logging.INFO)
