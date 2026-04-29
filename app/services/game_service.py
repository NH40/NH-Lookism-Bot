# Обратная совместимость — все импорты из других файлов продолжат работать
from app.services.game import GameService, game_service

__all__ = ["GameService", "game_service"]