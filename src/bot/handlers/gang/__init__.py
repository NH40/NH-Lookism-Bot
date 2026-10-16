"""Публичное API хендлеров домена gang."""
from bot.handlers.gang.gang import prompt_gang_name
from bot.handlers.gang.gang import router
from bot.handlers.gang.lineup import router as lineup_router

# Состав отряда — соседний файл домена со своим роутером; подключается к роутеру банды,
# чтобы `handlers/__init__.get_routers()` по-прежнему регистрировал один роутер на домен.
router.include_router(lineup_router)

__all__ = ["prompt_gang_name", "router"]
