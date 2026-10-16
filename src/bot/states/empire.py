from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class EmpireStates(StatesGroup):
    # Юзернейм игрока империи для персональной ставки налога.
    waiting_username = State()
