"""
Backward-compat shim — весь код перенесён в services/cards/*.py
Scheduler (tasks.py) и title_service.py импортируют отсюда deck_service.
"""
from app.services.cards.gacha import GachaService
from app.services.cards.fusion import FusionService
from app.services.cards.craft import CraftService
from app.services.cards.deck_slots import DeckSlotService


class DeckService(GachaService, FusionService, CraftService, DeckSlotService):
    """Объединяет все сервисы карточек в один класс для обратной совместимости."""
    pass


deck_service = DeckService()
