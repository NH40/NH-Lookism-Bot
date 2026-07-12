from app.services.bank.credits_service import credits_service, CreditsService
from app.services.bank.storage_service import storage_service, StorageService
from app.services.bank.investments_service import investments_service, InvestmentsService
from app.services.bank.casino import (
    slots_service, blackjack_service, casino_rating_service, poker_service,
)

__all__ = [
    "credits_service", "CreditsService",
    "storage_service", "StorageService",
    "investments_service", "InvestmentsService",
    "slots_service", "blackjack_service", "casino_rating_service", "poker_service",
]
