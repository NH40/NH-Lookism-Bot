"""Публичное API домена admin (сервис)."""
from bot.services.admin import audit, beta, players, roles  # noqa: F401
from bot.services.admin.admin import is_admin  # noqa: F401
