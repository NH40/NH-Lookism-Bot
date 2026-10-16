"""Публичное API домена storage (сервис)."""
from bot.services.storage.storage import (  # noqa: F401
    CellEmptyError,
    CellLockedError,
    CellOccupiedError,
    CellView,
    InvalidAmountError,
    NotEnoughCoinsError,
    NotEnoughError,
    StorageBusyError,
    cells,
    debt_for,
    open_cell,
    retrieve,
    store_resource,
    store_statists,
)
