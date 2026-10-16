from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class IntelStates(StatesGroup):
    # Юзернейм игрока для отчёта разведки.
    waiting_username = State()
