"""Публичное API домена error_log (сервис)."""
from bot.services.error_log.error_log import DbErrorHandler, flush, normalize, record_slow, run_sink  # noqa: F401
