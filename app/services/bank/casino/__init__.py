from app.services.bank.casino.common import CASINO_RESOURCES, CASINO_RESOURCE_LABELS
from app.services.bank.casino.slots_service import slots_service
from app.services.bank.casino.blackjack_service import blackjack_service
from app.services.bank.casino.rating_service import casino_rating_service
from app.services.bank.casino.poker_service import poker_service

__all__ = [
    "CASINO_RESOURCES", "CASINO_RESOURCE_LABELS",
    "slots_service", "blackjack_service", "casino_rating_service", "poker_service",
]
