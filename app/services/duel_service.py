"""
Сервис дуэлей карточек — перенесён в services/cards/duel.py.
Этот файл — shim для обратной совместимости.
"""
from app.services.cards.duel import DuelService, duel_service, build_user_team, team_power  # noqa: F401

__all__ = ["duel_service", "DuelService", "build_user_team", "team_power"]
