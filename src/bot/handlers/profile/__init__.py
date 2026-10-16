"""Публичное API хендлеров домена profile."""
from bot.handlers.profile.profile import router, show_profile
from bot.handlers.profile.stats import router as stats_router

# Экран характеристик — соседний файл домена со своим роутером, подключён внутрь роутера
# профиля (get_routers по-прежнему регистрирует один роутер на домен).
router.include_router(stats_router)

__all__ = ["router", "show_profile"]
