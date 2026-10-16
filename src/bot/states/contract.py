from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ContractStates(StatesGroup):
    # Количество наёмников выбранного ранга (ранг — в данных состояния).
    waiting_quantity = State()
