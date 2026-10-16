"""Публичное API домена deposit (сервис)."""
from bot.services.deposit.deposit import (  # noqa: F401
    DepositBusyError,
    DepositNotFoundError,
    DepositView,
    InvalidAmountError,
    InvalidTermError,
    NotEnoughError,
    TooManyDepositsError,
    cap_for,
    claim,
    list_deposits,
    open_deposit,
    rate_for,
)
