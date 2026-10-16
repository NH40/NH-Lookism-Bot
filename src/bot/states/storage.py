from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class StorageStates(StatesGroup):
    # Количество: положить ресурс/бойцов или достать часть. Что именно — в данных состояния
    # (slot, action, kind, code).
    waiting_amount = State()
