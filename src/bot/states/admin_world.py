from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminWorldStates(StatesGroup):
    waiting_city = State()  # название города
    waiting_owner = State()  # @ник/id нового владельца района (district_id в FSM-данных)
    waiting_emperor = State()  # @ник/id нового императора города (city_id в FSM-данных)
