from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class EmpireStates(StatesGroup):
    # Юзернейм игрока империи для персональной ставки налога.
    waiting_username = State()
    # Текст объявления игрокам империи.
    waiting_announcement = State()
    # Параметры ивента императора (вид — в данных состояния).
    waiting_event = State()
