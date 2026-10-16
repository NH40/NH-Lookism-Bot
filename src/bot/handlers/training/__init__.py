"""Публичное API хендлеров домена training."""
from bot.handlers.training.training import router  # noqa: F401
from bot.handlers.training.technique import router as technique_router  # noqa: F401,E402
from bot.handlers.training.schools import router as schools_router  # noqa: F401,E402
