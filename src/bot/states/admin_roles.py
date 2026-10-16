from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminRolesStates(StatesGroup):
    waiting_target = State()


class AdminConfigStates(StatesGroup):
    waiting_value = State()  # в данных: key
