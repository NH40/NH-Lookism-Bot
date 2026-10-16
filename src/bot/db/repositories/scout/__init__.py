"""Публичное API домена scout (репозиторий)."""
from bot.db.repositories.scout.scout import (  # noqa: F401
    delete_for,
    exists,
    get,
    recent,
    save,
)
