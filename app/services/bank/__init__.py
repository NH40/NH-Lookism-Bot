from app.services.bank.credits_service import credits_service, CreditsService
from app.services.bank.casino_service import casino_service, CasinoService
from app.services.bank.crypto_service import crypto_service, CryptoService
from app.services.bank.storage_service import storage_service, StorageService
from app.services.bank.investments_service import investments_service, InvestmentsService

__all__ = [
    "credits_service", "CreditsService",
    "casino_service", "CasinoService",
    "crypto_service", "CryptoService",
    "storage_service", "StorageService",
    "investments_service", "InvestmentsService",
]
