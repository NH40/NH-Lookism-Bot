from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class DepositStates(StatesGroup):
    # Сумма вклада; ресурс и срок — в данных состояния.
    waiting_amount = State()
